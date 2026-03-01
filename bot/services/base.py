"""Общая инфраструктура для доменных сервисов."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, Any

from hh_applicant_tool import HHApplicantTool

if TYPE_CHECKING:
    from bot.storage.protocol import StorageConnector

ProgressCallback = Callable[[str], Coroutine[Any, Any, None]]

_executor = ThreadPoolExecutor(max_workers=4)


async def run_sync(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Запускает блокирующую функцию в пуле потоков, не блокируя event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))


class BaseService:
    """Базовый класс доменных сервисов — работает с хранилищем через StorageConnector."""

    def __init__(self, storage: StorageConnector) -> None:
        self.storage = storage

    def _get_tool(self, user_id: int) -> HHApplicantTool:
        return HHApplicantTool(
            ["--config-dir", str(self.storage.get_work_dir(user_id))],
            config_backend=self.storage.get_config_backend(user_id),
            cookie_backend=self.storage.get_cookie_backend(user_id),
        )
