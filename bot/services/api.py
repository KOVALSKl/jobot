"""Сервис API — прямые вызовы к HH API."""

from __future__ import annotations

import json
import logging
from typing import Any

from bot.services.base import BaseService, run_sync

logger = logging.getLogger(__name__)


class ApiService(BaseService):
    """Выполнение произвольных запросов к HH API от имени пользователя."""

    async def call_api(
        self, user_id: int, method: str, endpoint: str, **params: Any
    ) -> str:
        """Вызывает эндпоинт HH API и возвращает JSON-ответ в виде строки."""
        tool = self._get_tool(user_id)
        methods = {"GET": tool.api_client.get, "POST": tool.api_client.post}
        fn = methods.get(method.upper(), tool.api_client.get)
        result = await run_sync(fn, endpoint, params or None)
        return json.dumps(result, indent=2, ensure_ascii=False)[:4000]
