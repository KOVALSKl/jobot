from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from hh_applicant_tool import HHApplicantTool
from hh_applicant_tool.api.errors import (
    ApiError,
    LimitExceeded,
)
from hh_applicant_tool.utils.string import rand_text, unescape_string

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Coroutine[Any, Any, None]]

_executor = ThreadPoolExecutor(max_workers=4)


async def _run_sync(func: Callable, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))


class HHService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _config_dir(self, user_id: int) -> Path:
        return self.data_dir / str(user_id)

    def _get_tool(self, user_id: int) -> HHApplicantTool:
        return HHApplicantTool(["--config-dir", str(self._config_dir(user_id))])

    # ── Auth ──────────────────────────────────────────────────────────

    def is_authenticated(self, user_id: int) -> bool:
        cfg_file = self._config_dir(user_id) / "config.json"
        if not cfg_file.exists():
            return False
        try:
            data = json.loads(cfg_file.read_text())
            return bool(data.get("token", {}).get("access_token"))
        except Exception:
            return False

    def save_tokens(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ) -> None:
        cfg_dir = self._config_dir(user_id)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "config.json"
        data: dict[str, Any] = {}
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text())
            except Exception:
                pass
        data["token"] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_expires_at": expires_at,
        }
        cfg_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_oauth_url(self, user_id: int) -> str:
        tool = self._get_tool(user_id)
        return tool.api_client.oauth_client.authorize_url

    def exchange_code(self, user_id: int, code: str) -> None:
        tool = self._get_tool(user_id)
        token = tool.api_client.oauth_client.authenticate(code)
        tool.api_client.handle_access_token(token)
        self.save_tokens(
            user_id,
            token["access_token"],
            token["refresh_token"],
            token["access_expires_at"],
        )

    def logout(self, user_id: int) -> None:
        cfg_file = self._config_dir(user_id) / "config.json"
        if cfg_file.exists():
            data = json.loads(cfg_file.read_text())
            data.pop("token", None)
            cfg_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ── Whoami ────────────────────────────────────────────────────────

    async def whoami(self, user_id: int) -> str:
        tool = self._get_tool(user_id)
        me = await _run_sync(tool.get_me)
        full_name = " ".join(
            filter(
                None,
                [
                    me.get("last_name"),
                    me.get("first_name"),
                    me.get("middle_name"),
                ],
            )
        ) or "Анонимный аккаунт"
        counters = me.get("counters", {})
        return (
            f"🆔 <b>{me['id']}</b> {full_name}\n"
            f"📄 Резюме: {counters.get('resumes_count', 0)}\n"
            f"👁️ Новые просмотры: +{counters.get('new_resume_views', 0)}\n"
            f"✉️ Непрочитанные: +{counters.get('unread_negotiations', 0)}"
        )

    # ── Resumes ───────────────────────────────────────────────────────

    async def list_resumes(self, user_id: int) -> str:
        tool = self._get_tool(user_id)
        resumes = await _run_sync(tool.get_resumes)
        if not resumes:
            return "У вас нет резюме."
        lines = ["📄 <b>Ваши резюме:</b>\n"]
        for r in resumes:
            status = r["status"]["name"]
            can_update = "🔄" if r.get("can_publish_or_update") else "⏸"
            lines.append(
                f"{can_update} <b>{r['title']}</b>\n"
                f"   Статус: {status}\n"
                f"   ID: <code>{r['id']}</code>"
            )
        return "\n\n".join(lines)

    async def update_resumes(self, user_id: int) -> str:
        tool = self._get_tool(user_id)
        resumes = await _run_sync(tool.get_resumes)
        updated = []
        errors = []
        for resume in resumes:
            if not resume.get("can_publish_or_update"):
                continue
            try:
                await _run_sync(
                    tool.api_client.post,
                    f"/resumes/{resume['id']}/publish",
                )
                updated.append(resume["title"])
            except ApiError as ex:
                errors.append(f"{resume['title']}: {ex}")
        if not updated and not errors:
            return "⏸ Нет резюме, доступных для обновления."
        parts = []
        if updated:
            titles = "\n".join(f"  ✅ {t}" for t in updated)
            parts.append(f"Обновлены:\n{titles}")
        if errors:
            errs = "\n".join(f"  ❌ {e}" for e in errors)
            parts.append(f"Ошибки:\n{errs}")
        return "\n\n".join(parts)

    # ── Refresh Token ─────────────────────────────────────────────────

    async def refresh_token(self, user_id: int) -> str:
        tool = self._get_tool(user_id)
        if tool.api_client.is_access_expired:
            await _run_sync(tool.api_client.refresh_access_token)
            token = tool.api_client.get_access_token()
            self.save_tokens(
                user_id,
                token["access_token"],
                token["refresh_token"],
                token["access_expires_at"],
            )
            return "✅ Токен успешно обновлён."
        return "ℹ️ Токен ещё не истёк, обновление не требуется."

    # ── Apply Similar ─────────────────────────────────────────────────

    async def apply_similar(
        self,
        user_id: int,
        callback: ProgressCallback,
        search: str | None = None,
        excluded_terms: str | None = None,
        message_template: str | None = None,
    ) -> None:
        tool = self._get_tool(user_id)
        resumes = await _run_sync(tool.get_resumes)
        published = [r for r in resumes if r["status"]["id"] == "published"]
        if not published:
            await callback("⚠️ У вас нет опубликованных резюме.")
            return

        me = await _run_sync(tool.get_me)
        excluded = _parse_excluded(excluded_terms)
        total_applied = 0
        total_skipped = 0
        limit_reached = False

        for resume in published:
            if limit_reached:
                break
            await callback(f"🚀 Рассылаю отклики с резюме: <b>{resume['title']}</b>")

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
                    res = await _run_sync(
                        tool.api_client.get,
                        f"/resumes/{resume['id']}/similar_vacancies",
                        params,
                    )
                except ApiError as ex:
                    await callback(f"❌ Ошибка загрузки вакансий: {ex}")
                    break

                items = res.get("items", [])
                if not items:
                    break

                for vacancy in items:
                    if limit_reached:
                        break
                    try:
                        if vacancy.get("relations"):
                            total_skipped += 1
                            continue
                        if vacancy.get("archived"):
                            total_skipped += 1
                            continue
                        if vacancy.get("response_url"):
                            total_skipped += 1
                            continue
                        if _is_excluded(vacancy, excluded):
                            total_skipped += 1
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

                        await _run_sync(
                            tool.api_client.post,
                            "/negotiations",
                            {
                                "resume_id": resume["id"],
                                "vacancy_id": vacancy["id"],
                                "message": msg,
                            },
                            delay=random.uniform(1, 3),
                        )
                        total_applied += 1

                        if total_applied % 10 == 0:
                            await callback(
                                f"📨 Отправлено откликов: {total_applied}..."
                            )

                    except LimitExceeded:
                        limit_reached = True
                        await callback("⚠️ Достигнут лимит откликов на сегодня.")
                    except ApiError as ex:
                        logger.warning("Apply error: %s", ex)
                        total_skipped += 1

                if page >= res.get("pages", 1) - 1:
                    break

        await callback(
            f"📝 <b>Рассылка завершена!</b>\n"
            f"✅ Отправлено: {total_applied}\n"
            f"⏭ Пропущено: {total_skipped}"
        )

    # ── Negotiations ──────────────────────────────────────────────────

    async def get_negotiations_summary(self, user_id: int) -> str:
        tool = self._get_tool(user_id)

        def _collect() -> tuple[dict[str, int], int]:
            s: dict[str, int] = {}
            c = 0
            for neg in tool.get_negotiations():
                sid = neg["state"]["id"]
                s[sid] = s.get(sid, 0) + 1
                c += 1
            return s, c

        stats, count = await _run_sync(_collect)

        if not count:
            return "У вас нет активных откликов."

        state_names = {
            "response": "📤 Отклик",
            "invitation": "📩 Приглашение",
            "discard": "⛔ Отказ",
            "phone_screen": "📞 Телефонное интервью",
        }
        lines = [f"📊 <b>Ваши отклики</b> (всего: {count})\n"]
        for state_id, cnt in sorted(stats.items(), key=lambda x: -x[1]):
            label = state_names.get(state_id, state_id)
            lines.append(f"  {label}: {cnt}")
        return "\n".join(lines)

    async def clear_negotiations(
        self,
        user_id: int,
        callback: ProgressCallback,
        older_than: int | None = None,
        blacklist: bool = False,
    ) -> None:
        tool = self._get_tool(user_id)

        def _collect_negotiations() -> list[dict]:
            return list(tool.get_negotiations())

        all_negs = await _run_sync(_collect_negotiations)
        cleared = 0

        blacklisted_ids: set[str] = set()
        if blacklist:
            blacklisted_ids = set(await _run_sync(tool.get_blacklisted))

        for neg in all_negs:
            vacancy = neg["vacancy"]
            should_clear = False

            if older_than:
                from hh_applicant_tool.utils.date import parse_api_datetime
                import datetime as dt

                updated = parse_api_datetime(neg["updated_at"])
                days = (dt.datetime.now(updated.tzinfo) - updated).days
                if days > older_than:
                    should_clear = True
            elif neg["state"]["id"] == "discard":
                should_clear = True

            if not should_clear:
                continue

            try:
                await _run_sync(
                    tool.api_client.delete,
                    f"/negotiations/active/{neg['id']}",
                    {"with_decline_message": True},
                )
                cleared += 1

                employer = vacancy.get("employer", {})
                employer_id = employer.get("id")
                if blacklist and employer_id and employer_id not in blacklisted_ids:
                    await _run_sync(
                        tool.api_client.put,
                        f"/employers/blacklisted/{employer_id}",
                    )
                    blacklisted_ids.add(employer_id)

            except ApiError as ex:
                logger.warning("Clear error: %s", ex)

        await callback(f"✅ Удалено откликов: {cleared}")

    async def reply_employers(
        self,
        user_id: int,
        callback: ProgressCallback,
        reply_message: str,
    ) -> None:
        tool = self._get_tool(user_id)
        me = await _run_sync(tool.get_me)
        resumes = await _run_sync(tool.get_resumes)
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

        all_negs = await _run_sync(_collect_negotiations)

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

                msgs_res = await _run_sync(
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

                await _run_sync(
                    tool.api_client.post,
                    f"/negotiations/{nid}/messages",
                    {"message": text},
                    delay=random.uniform(1, 3),
                )
                replied += 1

            except ApiError as ex:
                logger.warning("Reply error: %s", ex)

        await callback(f"📝 Отправлено ответов: {replied}")

    # ── Call API ──────────────────────────────────────────────────────

    async def call_api(
        self, user_id: int, method: str, endpoint: str, **params: Any
    ) -> str:
        tool = self._get_tool(user_id)
        methods = {"GET": tool.api_client.get, "POST": tool.api_client.post}
        fn = methods.get(method.upper(), tool.api_client.get)
        result = await _run_sync(fn, endpoint, params or None)
        return json.dumps(result, indent=2, ensure_ascii=False)[:4000]


def _parse_excluded(terms: str | None) -> list[str]:
    if not terms:
        return []
    return [x.strip().lower() for x in terms.split(",") if x.strip()]


def _is_excluded(vacancy: dict, excluded: list[str]) -> bool:
    if not excluded:
        return False
    snippet = vacancy.get("snippet") or {}
    combined = " ".join([
        vacancy.get("name") or "",
        snippet.get("requirement") or "",
        snippet.get("responsibility") or "",
    ]).lower()
    return any(t in combined for t in excluded)
