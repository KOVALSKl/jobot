"""Общая инфраструктура для доменных сервисов."""

from __future__ import annotations

from collections.abc import AsyncIterator
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from hh_applicant_tool import HHApplicantTool

from bot.services.concurrency import OperationGuard
from bot.services.hh_gateway import HHGateway
from bot.services.hh_gateway_async import AsyncHHGateway
from bot.services.hh_gateway_sync import SyncHHGateway
from bot.settings import HH_GATEWAY_MODE

if TYPE_CHECKING:
    from bot.storage.protocol import StorageConnector

ProgressCallback = Callable[[str], Coroutine[Any, Any, None]]


class BaseService:
    """Базовый класс доменных сервисов — работает с хранилищем через StorageConnector."""

    def __init__(
        self,
        storage: StorageConnector,
        operation_guard: OperationGuard | None = None,
        gateway_mode: str = HH_GATEWAY_MODE,
    ) -> None:
        self.storage = storage
        self._operation_guard = operation_guard or OperationGuard()
        self._gateway_mode = gateway_mode

    def _get_tool(self, user_id: int) -> HHApplicantTool:
        return HHApplicantTool(
            ["--config-dir", str(self.storage.get_work_dir(user_id))],
            config_backend=self.storage.get_config_backend(user_id),
            cookie_backend=self.storage.get_cookie_backend(user_id),
        )

    def _get_gateway(self, user_id: int) -> HHGateway:
        tool = self._get_tool(user_id)
        if self._gateway_mode == "sync":
            return SyncHHGateway(user_id=user_id, tool=tool)
        return AsyncHHGateway(user_id=user_id, tool=tool)

    @asynccontextmanager
    async def _gateway_context(self, user_id: int) -> AsyncIterator[HHGateway]:
        gateway = self._get_gateway(user_id)
        try:
            yield gateway
        finally:
            await gateway.aclose()

    async def _run_exclusive_heavy(self, operation: str, user_id: int, coro_factory):
        """Запускает тяжёлую операцию с per-user и global ограничителями."""
        return await self._operation_guard.run_exclusive_heavy(
            operation=operation, user_id=user_id, coro_factory=coro_factory
        )
