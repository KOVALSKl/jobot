"""Сервис откликов — массовый отклик на похожие вакансии."""

from __future__ import annotations

import logging
import random
from typing import Any

from hh_applicant_tool.api.errors import ApiError, LimitExceeded
from hh_applicant_tool.utils.string import rand_text, unescape_string

from bot.services.base import BaseService, ProgressCallback
from bot.services.concurrency import OperationInProgressError
from bot.services.vacancy_filter import (
    find_exclusion,
    normalize_exclude_mode,
    parse_excluded_terms,
)
from bot.texts import t

logger = logging.getLogger(__name__)


class ApplyService(BaseService):
    """Отправка откликов на вакансии, соответствующие опубликованным резюме пользователя."""

    async def apply_similar(
        self,
        user_id: int,
        callback: ProgressCallback,
        search: str | None = None,
        excluded_terms: str | None = None,
        exclude_mode: str | None = None,
        message_template: str | None = None,
    ) -> None:
        """Откликается на похожие вакансии для каждого опубликованного резюме."""
        async def _run() -> None:
            async with self._gateway_context(user_id) as gateway:
                resumes = await gateway.get_resumes()
                published = [r for r in resumes if r["status"]["id"] == "published"]
                if not published:
                    await callback(t("apply.no_published"))
                    return

                me = await gateway.get_me()
                mode = normalize_exclude_mode(exclude_mode)
                excluded = parse_excluded_terms(excluded_terms)
                total_applied = 0
                total_skipped = 0
                limit_reached = False

                for resume in published:
                    if limit_reached:
                        break
                    await callback(t("apply.resume_start", title=resume["title"]))

                    placeholders = {
                        "first_name": me.get("first_name") or "",
                        "last_name": me.get("last_name") or "",
                        "email": me.get("email") or "",
                        "phone": me.get("phone") or "",
                        "resume_title": resume.get("title") or "",
                    }

                    for page in range(20):
                        if limit_reached:
                            break
                        params: dict[str, Any] = {"page": page, "per_page": 100}
                        if search:
                            params["text"] = search

                        try:
                            res = await gateway.call_api(
                                method="GET",
                                endpoint=f"/resumes/{resume['id']}/similar_vacancies",
                                params=params,
                            )
                        except ApiError as ex:
                            await callback(t("apply.vacancies_error", error=str(ex)))
                            break

                        items = res.get("items", [])
                        if not items:
                            break

                        for vacancy in items:
                            if limit_reached:
                                break
                            vacancy_id = vacancy.get("id")
                            try:
                                if vacancy.get("relations"):
                                    total_skipped += 1
                                    logger.debug(
                                        "apply_skip reason=%s mode=%s vacancy_id=%s",
                                        "already_related",
                                        mode,
                                        vacancy_id,
                                    )
                                    continue
                                if vacancy.get("archived"):
                                    total_skipped += 1
                                    logger.debug(
                                        "apply_skip reason=%s mode=%s vacancy_id=%s",
                                        "archived",
                                        mode,
                                        vacancy_id,
                                    )
                                    continue
                                if vacancy.get("response_url"):
                                    total_skipped += 1
                                    logger.debug(
                                        "apply_skip reason=%s mode=%s vacancy_id=%s",
                                        "already_responded",
                                        mode,
                                        vacancy_id,
                                    )
                                    continue
                                decision = find_exclusion(
                                    vacancy=vacancy,
                                    excluded_terms=excluded,
                                    exclude_mode=mode,
                                )
                                if decision.is_excluded:
                                    total_skipped += 1
                                    logger.debug(
                                        "apply_skip reason=%s mode=%s vacancy_id=%s matched_term=%s term_len_bucket=%s",
                                        decision.reason,
                                        decision.mode,
                                        vacancy_id,
                                        decision.matched_term,
                                        decision.term_len_bucket,
                                    )
                                    continue

                                msg = ""
                                if message_template and (
                                    vacancy.get("response_letter_required")
                                    or message_template
                                ):
                                    msg_placeholders = {
                                        "vacancy_name": vacancy.get("name", ""),
                                        "employer_name": vacancy.get("employer", {}).get("name", ""),
                                        **placeholders,
                                    }
                                    try:
                                        msg = unescape_string(
                                            rand_text(message_template) % msg_placeholders
                                        )
                                    except Exception:
                                        msg = message_template

                                await gateway.create_negotiation(
                                    resume_id=resume["id"],
                                    vacancy_id=vacancy["id"],
                                    message=msg,
                                    delay=random.uniform(1, 3),
                                )
                                total_applied += 1

                                if total_applied % 10 == 0:
                                    await callback(t("apply.progress", count=total_applied))

                            except LimitExceeded:
                                limit_reached = True
                                await callback(t("apply.limit_reached"))
                            except ApiError as ex:
                                logger.warning("Apply error: %s", ex)
                                total_skipped += 1
                                logger.debug(
                                    "apply_skip reason=%s mode=%s vacancy_id=%s",
                                    "api_error",
                                    mode,
                                    vacancy_id,
                                )

                        if page >= res.get("pages", 1) - 1:
                            break

                await callback(t("apply.done", applied=total_applied, skipped=total_skipped))

        try:
            await self._run_exclusive_heavy("apply", user_id, _run)
        except OperationInProgressError:
            await callback("⚠️ Рассылка уже выполняется для этого пользователя.")
