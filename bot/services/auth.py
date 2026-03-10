"""Сервис аутентификации — токены, профиль, OAuth."""

from __future__ import annotations

import logging

from bot.services.base import BaseService
from bot.texts import t

logger = logging.getLogger(__name__)


class AuthService(BaseService):
    """Управление состоянием аутентификации HH: токены, вход, выход, профиль."""

    async def is_authenticated(self, user_id: int) -> bool:
        """Проверяет наличие действующего access-токена у пользователя."""
        if not await self.storage.config_exists(user_id):
            return False
        try:
            cfg = await self.storage.load_config(user_id)
            return bool(cfg.get("token", {}).get("access_token"))
        except Exception:
            return False

    async def save_tokens(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ) -> None:
        """Сохраняет OAuth-токены через коннектор хранилища."""
        await self.storage.save_config(
            user_id,
            {
                "token": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "access_expires_at": expires_at,
                }
            },
        )

    def get_oauth_url(self, user_id: int) -> str:
        """Возвращает URL авторизации HH OAuth."""
        tool = self._get_tool(user_id)
        try:
            return tool.api_client.oauth_client.authorize_url
        finally:
            if "session" in tool.__dict__:
                tool.session.close()
            if "db" in tool.__dict__:
                tool.db.close()

    async def exchange_code(self, user_id: int, code: str) -> None:
        """Обменивает OAuth-код на токены и сохраняет их."""
        async with self._gateway_context(user_id) as gateway:
            token = await gateway.exchange_code(code)
        await self.save_tokens(
            user_id,
            token["access_token"],
            token["refresh_token"],
            token["access_expires_at"],
        )

    async def logout(self, user_id: int) -> None:
        """Удаляет сохранённые токены пользователя."""
        await self.storage.delete_config_key(user_id, "token")

    # ── Async ─────────────────────────────────────────────────────────

    async def whoami(self, user_id: int) -> str:
        """Получает и форматирует сводку профиля HH пользователя."""
        async with self._gateway_context(user_id) as gateway:
            me = await gateway.get_me()
        full_name = " ".join(
            filter(
                None,
                [me.get("last_name"), me.get("first_name"), me.get("middle_name")],
            )
        ) or t("whoami.anonymous")
        counters = me.get("counters", {})
        return t(
            "whoami.info",
            id=me["id"],
            full_name=full_name,
            resumes_count=counters.get("resumes_count", 0),
            new_views=counters.get("new_resume_views", 0),
            unread=counters.get("unread_negotiations", 0),
        )

    async def refresh_token(self, user_id: int) -> str:
        """Обновляет access-токен, если он истёк."""
        async with self._gateway_context(user_id) as gateway:
            if await gateway.refresh_token_if_needed():
                return t("token.refreshed")
        return t("token.not_expired")
