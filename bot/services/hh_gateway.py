"""Контракты и общие утилиты gateway-слоя HH."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class HHGateway(Protocol):
    """Порт интеграции сервисов бота с HH API.

    Контракт одинаков для async primary и sync fallback адаптеров.
    """

    def get_oauth_url(self) -> str: ...

    async def exchange_code(self, code: str) -> dict[str, Any]: ...

    async def get_me(self) -> dict[str, Any]: ...

    async def get_resumes(self) -> list[dict[str, Any]]: ...

    async def get_negotiations(self, status: str = "active") -> list[dict[str, Any]]: ...

    async def get_blacklisted(self) -> list[str]: ...

    async def get_negotiation_messages(self, negotiation_id: str) -> dict[str, Any]: ...

    async def create_negotiation(
        self,
        resume_id: str,
        vacancy_id: str,
        message: str,
        delay: float | None = None,
    ) -> dict[str, Any]: ...

    async def delete_negotiation(self, negotiation_id: str) -> dict[str, Any]: ...

    async def blacklist_employer(self, employer_id: str) -> dict[str, Any]: ...

    async def publish_resume(self, resume_id: str) -> dict[str, Any]: ...

    async def call_api(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        delay: float | None = None,
    ) -> dict[str, Any]: ...

    async def refresh_token_if_needed(self) -> bool: ...

    async def aclose(self) -> None: ...


class GatewayInstrumentationMixin:
    """Структурированное логирование HH-вызовов с operation-id и latency."""

    def __init__(self, user_id: int) -> None:
        self._gateway_user_id = user_id

    async def _observe(
        self,
        operation: str,
        fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Оборачивает gateway-вызов общим логированием и таймингом."""
        operation_id = uuid.uuid4().hex
        started = time.perf_counter()
        logger.info(
            "hh_gateway_call_started operation_id=%s user_id=%s operation=%s",
            operation_id,
            self._gateway_user_id,
            operation,
        )
        try:
            rv = await fn()
        except TimeoutError as ex:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "hh_gateway_call_timeout operation_id=%s user_id=%s operation=%s latency_ms=%.2f error=%s",
                operation_id,
                self._gateway_user_id,
                operation,
                latency_ms,
                ex,
            )
            raise
        except Exception as ex:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "hh_gateway_call_failed operation_id=%s user_id=%s operation=%s latency_ms=%.2f error_type=%s error=%s",
                operation_id,
                self._gateway_user_id,
                operation,
                latency_ms,
                ex.__class__.__name__,
                ex,
            )
            raise

        latency_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "hh_gateway_call_succeeded operation_id=%s user_id=%s operation=%s latency_ms=%.2f",
            operation_id,
            self._gateway_user_id,
            operation,
            latency_ms,
        )
        return rv
