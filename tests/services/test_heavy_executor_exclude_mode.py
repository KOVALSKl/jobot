from __future__ import annotations

import asyncio
from typing import Any

from bot.services.heavy_executor import HeavyOperationExecutor
import bot.services.heavy_executor as heavy_executor_module


class _FakeStorage:
    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _CaptureApplyService:
    last_call: dict[str, Any] | None = None

    def __init__(self, storage: Any, operation_guard: Any) -> None:
        del storage
        del operation_guard

    async def apply_similar(
        self,
        user_id: int,
        callback,
        search: str | None = None,
        excluded_terms: str | None = None,
        exclude_mode: str | None = None,
        message_template: str | None = None,
    ) -> None:
        del callback
        self.__class__.last_call = {
            "user_id": user_id,
            "search": search,
            "excluded_terms": excluded_terms,
            "exclude_mode": exclude_mode,
            "message_template": message_template,
        }


def test_heavy_executor_passes_exclude_mode_to_apply_service() -> None:
    async def scenario() -> None:
        original_apply_service = heavy_executor_module.ApplyService
        heavy_executor_module.ApplyService = _CaptureApplyService  # type: ignore[assignment]
        _CaptureApplyService.last_call = None
        try:
            executor = HeavyOperationExecutor(storage=_FakeStorage())
            await executor.execute(
                user_id=10,
                operation="apply",
                payload={
                    "search": "python",
                    "excluded_terms": "c++, junior",
                    "exclude_mode": "partial_aggressive",
                    "message_template": "hi",
                },
                report_progress=lambda _: None,
                is_cancel_requested=lambda: False,
            )
        finally:
            heavy_executor_module.ApplyService = original_apply_service  # type: ignore[assignment]

        assert _CaptureApplyService.last_call is not None
        assert _CaptureApplyService.last_call["exclude_mode"] == "partial_aggressive"

    asyncio.run(scenario())


def test_heavy_executor_old_payload_without_mode_stays_backward_compatible() -> None:
    async def scenario() -> None:
        original_apply_service = heavy_executor_module.ApplyService
        heavy_executor_module.ApplyService = _CaptureApplyService  # type: ignore[assignment]
        _CaptureApplyService.last_call = None
        try:
            executor = HeavyOperationExecutor(storage=_FakeStorage())
            await executor.execute(
                user_id=11,
                operation="apply",
                payload={
                    "search": "python",
                    "excluded_terms": "junior",
                    "message_template": None,
                },
                report_progress=lambda _: None,
                is_cancel_requested=lambda: False,
            )
        finally:
            heavy_executor_module.ApplyService = original_apply_service  # type: ignore[assignment]

        assert _CaptureApplyService.last_call is not None
        assert _CaptureApplyService.last_call["exclude_mode"] is None

    asyncio.run(scenario())
