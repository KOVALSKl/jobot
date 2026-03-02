"""Переиспользуемые декораторы для обработчиков бота."""

from __future__ import annotations

from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message

from bot.texts import t


def require_auth(func: Any) -> Any:
    """Блокирует выполнение обработчика, если пользователь не авторизован в HH."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        event: Message | CallbackQuery = args[0]
        auth_service = kwargs["auth_service"]
        user_id = event.from_user.id

        if not await auth_service.is_authenticated(user_id):
            text = t("common.not_authorized")
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return None

        return await func(*args, **kwargs)

    return wrapper
