from __future__ import annotations

from datetime import UTC, datetime

from bot.models import UserTask
from bot.services.heavy_queue import render_task_status


def test_render_task_status_none() -> None:
    text = render_task_status(None)
    assert "нет фоновых задач" in text


def test_render_task_status_includes_progress() -> None:
    task = UserTask(
        task_id="abc123",
        user_id=1,
        operation="apply",
        status="running",
        payload={},
        progress="Отправлено 10 откликов",
        created_at=datetime.now(UTC),
    )
    text = render_task_status(task)
    assert "abc123" in text
    assert "Отправлено 10 откликов" in text
