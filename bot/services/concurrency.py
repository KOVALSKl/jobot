"""Ограничители параллелизма для тяжёлых пользовательских операций."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class OperationInProgressError(RuntimeError):
    """Операция для пользователя уже выполняется."""


class OperationGuard:
    """Управляет конкурентным запуском тяжёлых операций."""

    def __init__(
        self,
        max_global_heavy_tasks: int = 8,
        operation_cooldown_seconds: int = 30,
    ) -> None:
        self._global_heavy_semaphore = asyncio.Semaphore(max_global_heavy_tasks)
        self._user_locks: dict[int, asyncio.Lock] = {}
        self._operation_cooldown_seconds = operation_cooldown_seconds
        self._last_operation_time: dict[tuple[int, str], float] = {}

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        lock = self._user_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock
        return lock

    async def run_exclusive_heavy(
        self,
        operation: str,
        user_id: int,
        coro_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Запускает тяжёлую операцию с per-user эксклюзивностью и общим лимитом."""
        now = asyncio.get_running_loop().time()
        last_run = self._last_operation_time.get((user_id, operation))
        if (
            last_run is not None
            and now - last_run < self._operation_cooldown_seconds
        ):
            raise OperationInProgressError(
                f"Слишком частый повтор '{operation}' для пользователя {user_id}"
            )

        user_lock = self._get_user_lock(user_id)
        if user_lock.locked():
            raise OperationInProgressError(
                f"Тяжёлая операция уже выполняется для пользователя {user_id}"
            )
        async with self._global_heavy_semaphore:
            async with user_lock:
                result = await coro_factory()
                self._last_operation_time[(user_id, operation)] = (
                    asyncio.get_running_loop().time()
                )
                return result

