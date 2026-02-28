"""Сервис откликов — сводка, очистка и ответы работодателям."""

from __future__ import annotations

import datetime as dt
import logging
import random

from hh_applicant_tool.api.errors import ApiError
from hh_applicant_tool.utils.date import parse_api_datetime
from hh_applicant_tool.utils.string import rand_text, unescape_string

from bot.services.base import BaseService, ProgressCallback, run_sync
from bot.texts import NEGOTIATION_STATES, t

logger = logging.getLogger(__name__)


class NegotiationService(BaseService):
    """Управление откликами HH: просмотр, очистка и ответы."""

    async def get_summary(self, user_id: int) -> str:
        """Возвращает отформатированную сводку количества откликов по статусам."""
        tool = self._get_tool(user_id)

        def _collect() -> tuple[dict[str, int], int]:
            stats: dict[str, int] = {}
            total = 0
            for neg in tool.get_negotiations():
                sid = neg["state"]["id"]
                stats[sid] = stats.get(sid, 0) + 1
                total += 1
            return stats, total

        stats, count = await run_sync(_collect)

        if not count:
            return t("negotiations.empty")

        lines = [t("negotiations.header", count=count)]
        for state_id, cnt in sorted(stats.items(), key=lambda x: -x[1]):
            label = NEGOTIATION_STATES.get(state_id, state_id)
            lines.append(f"  {label}: {cnt}")
        return "\n".join(lines)

    async def clear(
        self,
        user_id: int,
        callback: ProgressCallback,
        older_than: int | None = None,
        blacklist: bool = False,
    ) -> None:
        """Удаляет отклики по заданным критериям и опционально добавляет работодателей в чёрный список."""
        tool = self._get_tool(user_id)

        def _collect_negotiations() -> list[dict]:
            return list(tool.get_negotiations())

        all_negs = await run_sync(_collect_negotiations)
        cleared = 0

        blacklisted_ids: set[str] = set()
        if blacklist:
            blacklisted_ids = set(await run_sync(tool.get_blacklisted))

        for neg in all_negs:
            vacancy = neg["vacancy"]
            should_clear = False

            if older_than:
                updated = parse_api_datetime(neg["updated_at"])
                days = (dt.datetime.now(updated.tzinfo) - updated).days
                if days > older_than:
                    should_clear = True
            elif neg["state"]["id"] == "discard":
                should_clear = True

            if not should_clear:
                continue

            try:
                await run_sync(
                    tool.api_client.delete,
                    f"/negotiations/active/{neg['id']}",
                    {"with_decline_message": True},
                )
                cleared += 1

                employer = vacancy.get("employer", {})
                employer_id = employer.get("id")
                if blacklist and employer_id and employer_id not in blacklisted_ids:
                    await run_sync(
                        tool.api_client.put,
                        f"/employers/blacklisted/{employer_id}",
                    )
                    blacklisted_ids.add(employer_id)

            except ApiError as ex:
                logger.warning("Clear error: %s", ex)

        await callback(t("negotiations.cleared", count=cleared))

    async def reply_employers(
        self,
        user_id: int,
        callback: ProgressCallback,
        reply_message: str,
    ) -> None:
        """Отправляет шаблонные ответы на непрочитанные сообщения работодателей."""
        tool = self._get_tool(user_id)
        me = await run_sync(tool.get_me)
        resumes = await run_sync(tool.get_resumes)
        published = [r for r in resumes if r["status"]["id"] == "published"]
        resume_map = {r["id"]: r for r in published}
        replied = 0

        base_placeholders = {
            "first_name": me.get("first_name") or "",
            "last_name": me.get("last_name") or "",
            "email": me.get("email") or "",
            "phone": me.get("phone") or "",
        }

        def _collect_negotiations() -> list[dict]:
            return list(tool.get_negotiations())

        all_negs = await run_sync(_collect_negotiations)

        for neg in all_negs:
            try:
                resume = resume_map.get(neg["resume"]["id"])
                if not resume:
                    continue

                if neg["state"]["id"] == "discard":
                    continue

                nid = neg["id"]
                vacancy = neg["vacancy"]
                employer = vacancy.get("employer") or {}

                msgs_res = await run_sync(
                    tool.api_client.get, f"/negotiations/{nid}/messages"
                )
                items = msgs_res.get("items", [])
                if not items:
                    continue
                last_msg = items[-1]

                is_employer_msg = (
                    last_msg["author"]["participant_type"] == "employer"
                )
                if not is_employer_msg and neg.get("viewed_by_opponent"):
                    continue

                placeholders = {
                    "vacancy_name": vacancy.get("name", ""),
                    "employer_name": employer.get("name", ""),
                    "resume_title": resume.get("title") or "",
                    **base_placeholders,
                }
                try:
                    text = unescape_string(
                        rand_text(reply_message) % placeholders
                    )
                except Exception:
                    text = reply_message

                await run_sync(
                    tool.api_client.post,
                    f"/negotiations/{nid}/messages",
                    {"message": text},
                    delay=random.uniform(1, 3),
                )
                replied += 1

            except ApiError as ex:
                logger.warning("Reply error: %s", ex)

        await callback(t("reply.done", count=replied))
