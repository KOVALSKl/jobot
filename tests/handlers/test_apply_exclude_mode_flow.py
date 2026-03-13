from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import bot.handlers.apply as apply_handlers
from bot.states import ApplyStates


class _FakeState:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.state: Any = None

    async def clear(self) -> None:
        self.data.clear()
        self.state = None

    async def set_state(self, state: Any) -> None:
        self.state = state

    async def update_data(self, **kwargs: Any) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, Any]:
        return dict(self.data)


class _FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append({"text": text, "kwargs": kwargs})

    async def edit_text(self, text: str, **kwargs: Any):
        self.edits.append({"text": text, "kwargs": kwargs})
        return self


class _FakeCallback:
    def __init__(self, data: str, message: _FakeMessage) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=123)

    async def answer(self) -> None:
        return None


def test_apply_excluded_moves_to_mode_selection() -> None:
    async def scenario() -> None:
        state = _FakeState()
        message = _FakeMessage(text="c, c++")
        await apply_handlers.apply_excluded_received(message, state)  # type: ignore[arg-type]
        assert state.state == ApplyStates.waiting_for_exclude_mode
        assert state.data["excluded"] == "c, c++"
        assert "режим фильтрации" in message.answers[-1]["text"]

    asyncio.run(scenario())


def test_partial_mode_with_single_char_requires_risk_confirmation() -> None:
    async def scenario() -> None:
        state = _FakeState()
        await state.update_data(excluded="c, c++")
        callback_message = _FakeMessage()
        callback = _FakeCallback(
            data="apply_mode_partial_aggressive",
            message=callback_message,
        )
        await apply_handlers.apply_mode_selected(callback, state)  # type: ignore[arg-type]
        assert state.state == ApplyStates.waiting_for_partial_confirm
        assert "короткие исключения" in callback_message.edits[-1]["text"]

    asyncio.run(scenario())


def test_run_apply_inline_passes_exclude_mode() -> None:
    async def scenario() -> None:
        captured: dict[str, Any] = {}
        original_mode = apply_handlers.HEAVY_TASKS_MODE
        original_runner = apply_handlers.run_heavy_operation
        try:
            apply_handlers.HEAVY_TASKS_MODE = "inline"

            async def fake_run_heavy_operation(**kwargs: Any) -> str:
                captured.update(kwargs)
                progress = kwargs["report_progress"]
                await progress("tick")
                return "ok"

            apply_handlers.run_heavy_operation = fake_run_heavy_operation  # type: ignore[assignment]
            message = _FakeMessage()
            await apply_handlers._run_apply(  # type: ignore[arg-type]
                message=message,
                user_id=123,
                search="python",
                excluded="c",
                exclude_mode="partial_aggressive",
                message_template=None,
            )
        finally:
            apply_handlers.HEAVY_TASKS_MODE = original_mode
            apply_handlers.run_heavy_operation = original_runner  # type: ignore[assignment]

        payload = captured["payload"]
        assert payload["exclude_mode"] == "partial_aggressive"

    asyncio.run(scenario())


def test_run_apply_celery_passes_exclude_mode() -> None:
    async def scenario() -> None:
        captured: dict[str, Any] = {}
        original_mode = apply_handlers.HEAVY_TASKS_MODE
        original_scheduler = apply_handlers.schedule_heavy_task
        try:
            apply_handlers.HEAVY_TASKS_MODE = "celery"

            async def fake_schedule_heavy_task(**kwargs: Any):
                captured.update(kwargs)
                return SimpleNamespace(task_id="task-1")

            apply_handlers.schedule_heavy_task = fake_schedule_heavy_task  # type: ignore[assignment]
            message = _FakeMessage()
            await apply_handlers._run_apply(  # type: ignore[arg-type]
                message=message,
                user_id=123,
                search="python",
                excluded="c",
                exclude_mode="partial_aggressive",
                message_template=None,
            )
        finally:
            apply_handlers.HEAVY_TASKS_MODE = original_mode
            apply_handlers.schedule_heavy_task = original_scheduler  # type: ignore[assignment]

        payload = captured["payload"]
        assert payload["exclude_mode"] == "partial_aggressive"

    asyncio.run(scenario())
