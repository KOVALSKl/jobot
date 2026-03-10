"""Celery задачи для тяжёлых операций."""

from __future__ import annotations

import asyncio
from typing import Any

from bot.celery_app import celery_app
from bot.services.heavy_executor import TaskCancelledError, run_heavy_operation
from bot.services.tasks import SyncTaskStore

async def _run_heavy_operation(task_id: str, operation: str, payload: dict[str, Any]) -> str:
    """Async bridge: проксирует прогресс/cancel в SyncTaskStore для worker."""
    store = SyncTaskStore()
    return await run_heavy_operation(
        operation=operation,
        payload=payload,
        report_progress=lambda text: store.set_progress(task_id, text),
        is_cancel_requested=lambda: store.is_cancel_requested(task_id),
    )


@celery_app.task(bind=True, name="bot.run_heavy_task")
def run_heavy_task(self, task_id: str, operation: str, payload: dict[str, Any]) -> str:
    """Запускает тяжёлую операцию из очереди Celery."""
    store = SyncTaskStore()
    task = store.get_task(task_id)
    if task is None:
        return "Task not found"
    if task.status == "cancelled":
        return "Task was cancelled before start"

    store.mark_running(task_id)
    try:
        # В worker-процессе Celery выполняем общий async executor через
        # `asyncio.run`, сохраняя единый контракт с inline-режимом.
        result = asyncio.run(_run_heavy_operation(task_id, operation, payload))
        store.mark_success(task_id, result)
        return result
    except TaskCancelledError as ex:
        store.mark_cancelled(task_id, str(ex))
        return str(ex)
    except Exception as ex:  # pragma: no cover - защищаем worker
        store.mark_failed(task_id, str(ex))
        raise
