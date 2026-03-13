"""Единый executor тяжёлых доменных операций."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Any

from bot.services import ApplyService, NegotiationService, ResumeService
from bot.services.concurrency import OperationGuard
from bot.storage.protocol import StorageConnector
from bot.settings import create_storage


class TaskCancelledError(RuntimeError):
    """Фоновая задача отменена пользователем."""


ProgressReporter = Callable[[str], Awaitable[None] | None]
CancelChecker = Callable[[], bool]


class HeavyOperationExecutor:
    """Единый async entrypoint тяжёлых операций apply/clear/reply/update.

    Инвариант: и inline, и celery-режим используют одинаковую orchestration
    логику, чтобы исключить расхождения поведения между окружениями.
    """

    def __init__(
        self,
        storage: StorageConnector,
        operation_guard: OperationGuard | None = None,
    ) -> None:
        self._storage = storage
        self._guard = operation_guard or OperationGuard(max_global_heavy_tasks=1)

    async def execute(
        self,
        user_id: int,
        operation: str,
        payload: dict[str, Any],
        report_progress: ProgressReporter,
        is_cancel_requested: CancelChecker,
    ) -> str:
        """Исполняет heavy-операцию и возвращает итоговое сообщение.

        Raises:
            TaskCancelledError: если операция отменена пользователем.
            RuntimeError: если указан неподдерживаемый тип операции.
        """
        async def make_progress(message: str) -> None:
            progress_result = report_progress(message)
            if isawaitable(progress_result):
                await progress_result
            if is_cancel_requested():
                raise TaskCancelledError("Операция отменена")

        if operation == "apply":
            service = ApplyService(storage=self._storage, operation_guard=self._guard)
            await service.apply_similar(
                user_id=user_id,
                callback=make_progress,
                search=payload.get("search"),
                excluded_terms=payload.get("excluded_terms"),
                exclude_mode=payload.get("exclude_mode"),
                message_template=payload.get("message_template"),
            )
            return "Рассылка откликов завершена"

        if operation == "clear":
            service = NegotiationService(storage=self._storage, operation_guard=self._guard)
            await service.clear(
                user_id=user_id,
                callback=make_progress,
                older_than=payload.get("older_than"),
                blacklist=bool(payload.get("blacklist", False)),
            )
            return "Очистка откликов завершена"

        if operation == "reply":
            service = NegotiationService(storage=self._storage, operation_guard=self._guard)
            await service.reply_employers(
                user_id=user_id,
                callback=make_progress,
                reply_message=str(payload.get("reply_message", "")),
            )
            return "Ответы работодателям отправлены"

        if operation == "update":
            service = ResumeService(storage=self._storage, operation_guard=self._guard)
            if is_cancel_requested():
                raise TaskCancelledError("Операция отменена")
            result = await service.update_resumes(user_id=user_id)
            await make_progress(result)
            return result

        raise RuntimeError(f"Unsupported operation: {operation}")


async def run_heavy_operation(
    operation: str,
    payload: dict[str, Any],
    report_progress: ProgressReporter,
    is_cancel_requested: CancelChecker,
) -> str:
    """Общий orchestration для inline/celery запусков heavy-операций.

    Side effects:
    - инициализирует и закрывает хранилище в рамках одного запуска операции;
    - делегирует фактическое выполнение `HeavyOperationExecutor`.
    """
    user_id = int(payload["user_id"])
    storage = create_storage()
    await storage.init()
    executor = HeavyOperationExecutor(
        storage=storage,
        operation_guard=OperationGuard(max_global_heavy_tasks=1),
    )
    try:
        return await executor.execute(
            user_id=user_id,
            operation=operation,
            payload=payload,
            report_progress=report_progress,
            is_cancel_requested=is_cancel_requested,
        )
    finally:
        await storage.close()
