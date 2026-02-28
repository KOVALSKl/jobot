"""Мидлвары aiogram для бота."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import config
from bot.texts import t


class AccessControlMiddleware(BaseMiddleware):
    """Отклоняет события от пользователей, не указанных в списке разрешённых."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and not config.is_user_allowed(user.id):
            if isinstance(event, Message):
                await event.answer(t("middleware.no_access"))
            elif isinstance(event, CallbackQuery):
                await event.answer(t("middleware.no_access_short"), show_alert=True)
            return None

        return await handler(event, data)
