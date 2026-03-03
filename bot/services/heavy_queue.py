"""Постановка тяжёлых задач в очередь и форматирование статусов."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bot.celery_app import celery_app
from bot.models import UserTask
from bot.services.tasks import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_CANCEL_REQUESTED,
    TASK_STATUS_FAILED,
    TASK_STATUS_QUEUED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCESS,
    GlobalTaskLimitError,
    TaskAlreadyRunningError,
    TaskCooldownError,
    TaskQueueService,
)
from bot.settings import HEAVY_TASKS_MODE


def _format_eta(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек."
    mins = max(1, seconds // 60)
    return f"{mins} мин."


async def schedule_heavy_task(
    user_id: int,
    operation: str,
    payload: dict[str, Any],
) -> UserTask:
    """Создаёт запись задачи и, при режиме celery, отправляет её в очередь."""
    queue = TaskQueueService()
    task = await queue.enqueue(user_id=user_id, operation=operation, payload=payload)
    if HEAVY_TASKS_MODE == "celery":
        payload_with_user = {"user_id": user_id, **payload}
        async_result = celery_app.send_task(
            "bot.run_heavy_task",
            kwargs={
                "task_id": task.task_id,
                "operation": operation,
                "payload": payload_with_user,
            },
            task_id=task.task_id,
        )
        await queue.attach_celery_id(task.task_id, async_result.id)
    return task


async def cancel_user_task(user_id: int, task_id: str | None = None) -> UserTask | None:
    """Помечает активную задачу как отменённую/отменяемую и отзывает Celery-задачу."""
    queue = TaskQueueService()
    task = await queue.request_cancel(user_id=user_id, task_id=task_id)
    if task is None:
        return None
    if task.celery_task_id:
        celery_app.control.revoke(task.celery_task_id, terminate=False)
    return task


def format_queue_error(ex: Exception) -> str:
    if isinstance(ex, TaskAlreadyRunningError):
        return "⚠️ У вас уже выполняется тяжёлая задача. Дождитесь завершения."
    if isinstance(ex, GlobalTaskLimitError):
        return "⚠️ Сейчас система перегружена. Попробуйте позже."
    if isinstance(ex, TaskCooldownError):
        return (
            "⚠️ Эту операцию недавно запускали. "
            f"Повторите через {_format_eta(ex.retry_after_seconds)}"
        )
    return f"❌ Ошибка планирования задачи: {ex}"


def render_task_status(task: UserTask | None) -> str:
    """Человекочитаемый статус задачи для пользователя."""
    if task is None:
        return "ℹ️ У вас пока нет фоновых задач."

    status_map = {
        TASK_STATUS_QUEUED: "⏳ В очереди",
        TASK_STATUS_RUNNING: "🚀 Выполняется",
        TASK_STATUS_CANCEL_REQUESTED: "🛑 Запрошена отмена",
        TASK_STATUS_CANCELLED: "❌ Отменена",
        TASK_STATUS_SUCCESS: "✅ Завершена",
        TASK_STATUS_FAILED: "❌ Завершилась с ошибкой",
    }
    created = task.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"🧾 Задача: <code>{task.task_id}</code>",
        f"⚙️ Операция: <b>{task.operation}</b>",
        f"📌 Статус: {status_map.get(task.status, task.status)}",
        f"🕒 Создана: {created}",
    ]
    if task.progress:
        lines.append(f"📈 Прогресс: {task.progress}")
    if task.result_text:
        lines.append(f"✅ Результат: {task.result_text}")
    if task.error_text:
        lines.append(f"❌ Ошибка: {task.error_text}")
    return "\n".join(lines)
