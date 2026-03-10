"""Сервис резюме — получение списка и обновление резюме HH."""

from __future__ import annotations

import logging

from hh_applicant_tool.api.errors import ApiError

from bot.services.base import BaseService
from bot.texts import t

logger = logging.getLogger(__name__)


class ResumeService(BaseService):
    """Получение списка и обновление резюме пользователя на HH."""

    async def list_resumes(self, user_id: int) -> str:
        """Возвращает отформатированный список всех резюме пользователя."""
        async with self._gateway_context(user_id) as gateway:
            resumes = await gateway.get_resumes()
        if not resumes:
            return t("resumes.empty")
        lines = [t("resumes.header")]
        for r in resumes:
            icon = "🔄" if r.get("can_publish_or_update") else "⏸"
            lines.append(t(
                "resumes.item",
                icon=icon,
                title=r["title"],
                status=r["status"]["name"],
                id=r["id"],
            ))
        return "\n\n".join(lines)

    async def update_resumes(self, user_id: int) -> str:
        """Публикует/поднимает все доступные для обновления резюме и возвращает отчёт."""
        async with self._gateway_context(user_id) as gateway:
            resumes = await gateway.get_resumes()
            updated: list[str] = []
            errors: list[str] = []
            for resume in resumes:
                if not resume.get("can_publish_or_update"):
                    continue
                try:
                    await gateway.publish_resume(resume["id"])
                    updated.append(resume["title"])
                except ApiError as ex:
                    errors.append(f"{resume['title']}: {ex}")
        if not updated and not errors:
            return t("resumes.no_updates")
        parts: list[str] = []
        if updated:
            titles = "\n".join(t("resumes.updated_item", title=x) for x in updated)
            parts.append(t("resumes.updated_section", titles=titles))
        if errors:
            errs = "\n".join(t("resumes.error_item", error=x) for x in errors)
            parts.append(t("resumes.error_section", errors=errs))
        return "\n\n".join(parts)
