"""Celery задачи для тяжёлых операций."""

from __future__ import annotations

import asyncio
from typing import Any

from bot.celery_app import celery_app
from bot.services import ApplyService, NegotiationService, ResumeService
from bot.services.concurrency import OperationGuard
from bot.services.tasks import SyncTaskStore
from bot.settings import create_storage


class TaskCancelledError(RuntimeError):
    """Фоновая задача отменена пользователем."""


async def _run_heavy_operation(task_id: str, operation: str, payload: dict[str, Any]) -> str:
    user_id = int(payload["user_id"])
    store = SyncTaskStore()
    storage = create_storage()
    await storage.init()
    guard = OperationGuard(max_global_heavy_tasks=1)
    try:
        if operation == "apply":
            service = ApplyService(storage=storage, operation_guard=guard)

            async def progress(text: str) -> None:
                store.set_progress(task_id, text)
                if store.is_cancel_requested(task_id):
                    raise TaskCancelledError("Операция отменена")

            await service.apply_similar(
                user_id=user_id,
                callback=progress,
                search=payload.get("search"),
                excluded_terms=payload.get("excluded_terms"),
                message_template=payload.get("message_template"),
            )
            return "Рассылка откликов завершена"

        if operation == "clear":
            service = NegotiationService(storage=storage, operation_guard=guard)

            async def progress(text: str) -> None:
                store.set_progress(task_id, text)
                if store.is_cancel_requested(task_id):
                    raise TaskCancelledError("Операция отменена")

            await service.clear(
                user_id=user_id,
                callback=progress,
                older_than=payload.get("older_than"),
                blacklist=bool(payload.get("blacklist", False)),
            )
            return "Очистка откликов завершена"

        if operation == "reply":
            service = NegotiationService(storage=storage, operation_guard=guard)

            async def progress(text: str) -> None:
                store.set_progress(task_id, text)
                if store.is_cancel_requested(task_id):
                    raise TaskCancelledError("Операция отменена")

            await service.reply_employers(
                user_id=user_id,
                callback=progress,
                reply_message=str(payload.get("reply_message", "")),
            )
            return "Ответы работодателям отправлены"

        if operation == "update":
            service = ResumeService(storage=storage, operation_guard=guard)
            if store.is_cancel_requested(task_id):
                raise TaskCancelledError("Операция отменена")
            result = await service.update_resumes(user_id=user_id)
            store.set_progress(task_id, result)
            return result

        raise RuntimeError(f"Unsupported operation: {operation}")
    finally:
        await storage.close()


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
        result = asyncio.run(_run_heavy_operation(task_id, operation, payload))
        store.mark_success(task_id, result)
        return result
    except TaskCancelledError as ex:
        store.mark_cancelled(task_id, str(ex))
        return str(ex)
    except Exception as ex:  # pragma: no cover - защищаем worker
        store.mark_failed(task_id, str(ex))
        raise
