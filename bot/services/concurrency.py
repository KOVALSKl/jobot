"""Ограничители параллелизма для тяжёлых пользовательских операций."""

from __future__ import annotations

import asyncio


class OperationInProgressError(RuntimeError):
    """Операция для пользователя уже выполняется."""


class OperationGuard:
    """Управляет конкурентным запуском тяжёлых операций."""

    def __init__(self, max_global_heavy_tasks: int = 8) -> None:
        self._global_heavy_semaphore = asyncio.Semaphore(max_global_heavy_tasks)
        self._user_locks: dict[tuple[str, int], asyncio.Lock] = {}

    def _get_user_lock(self, operation: str, user_id: int) -> asyncio.Lock:
        key = (operation, user_id)
        lock = self._user_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[key] = lock
        return lock

    async def run_exclusive_heavy(
        self,
        operation: str,
        user_id: int,
        coro_factory,
    ):
        """Запускает тяжёлую операцию с per-user эксклюзивностью и общим лимитом."""
        user_lock = self._get_user_lock(operation, user_id)
        if user_lock.locked():
            raise OperationInProgressError(
                f"Операция '{operation}' уже выполняется для пользователя {user_id}"
            )
        async with self._global_heavy_semaphore:
            async with user_lock:
                return await coro_factory()

