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


class _FakeApplyService:
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
        del user_id
        del search
        del excluded_terms
        del exclude_mode
        del message_template
        await callback("progress-step")


def test_executor_awaits_progress_reporter_before_returning_final_result() -> None:
    async def scenario() -> None:
        events: list[str] = []
        original_apply_service = heavy_executor_module.ApplyService
        heavy_executor_module.ApplyService = _FakeApplyService  # type: ignore[assignment]
        try:
            executor = HeavyOperationExecutor(storage=_FakeStorage())

            async def delayed_append(text: str) -> None:
                await asyncio.sleep(0.01)
                events.append(f"progress:{text}")

            def report_progress(text: str):
                return asyncio.create_task(delayed_append(text))

            result = await executor.execute(
                user_id=1,
                operation="apply",
                payload={},
                report_progress=report_progress,
                is_cancel_requested=lambda: False,
            )
            events.append(f"final:{result}")
            await asyncio.sleep(0.02)
        finally:
            heavy_executor_module.ApplyService = original_apply_service  # type: ignore[assignment]

        assert events == [
            "progress:progress-step",
            "final:Рассылка откликов завершена",
        ]

    asyncio.run(scenario())
