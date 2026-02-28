"""Общая инфраструктура для доменных сервисов."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from hh_applicant_tool import HHApplicantTool
from hh_applicant_tool.utils.config import Config

ProgressCallback = Callable[[str], Coroutine[Any, Any, None]]

_executor = ThreadPoolExecutor(max_workers=4)


async def run_sync(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Запускает блокирующую функцию в пуле потоков, не блокируя event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))


class BaseService:
    """Базовый класс доменных сервисов — предоставляет хелперы для конфигурации и инструментов."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _config_dir(self, user_id: int) -> Path:
        return self.data_dir / str(user_id)

    def _config_path(self, user_id: int) -> Path:
        return self._config_dir(user_id) / "config.json"

    def _get_config(self, user_id: int) -> Config:
        return Config(self._config_path(user_id))

    def _get_tool(self, user_id: int) -> HHApplicantTool:
        return HHApplicantTool(["--config-dir", str(self._config_dir(user_id))])
