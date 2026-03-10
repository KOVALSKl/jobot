"""Сервис API — прямые вызовы к HH API."""

from __future__ import annotations

import json
import logging
from typing import Any

from bot.services.base import BaseService

logger = logging.getLogger(__name__)


class ApiService(BaseService):
    """Выполнение произвольных запросов к HH API от имени пользователя."""

    async def call_api(
        self, user_id: int, method: str, endpoint: str, **params: Any
    ) -> str:
        """Вызывает эндпоинт HH API и возвращает JSON-ответ в виде строки."""
        async with self._gateway_context(user_id) as gateway:
            result = await gateway.call_api(
                method=method,
                endpoint=endpoint,
                params=params or None,
            )
        return json.dumps(result, indent=2, ensure_ascii=False)[:4000]
