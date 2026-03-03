"""Управление очередью тяжёлых пользовательских задач."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from bot.database import get_session_factory
from bot.models import UserTask
from bot.settings import (
    DATABASE_URL,
    HEAVY_TASK_COOLDOWN_SECONDS,
    HEAVY_TASK_GLOBAL_LIMIT,
)

TASK_STATUS_QUEUED = "queued"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCEL_REQUESTED = "cancel_requested"
TASK_STATUS_CANCELLED = "cancelled"

ACTIVE_TASK_STATUSES = {
    TASK_STATUS_QUEUED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_CANCEL_REQUESTED,
}


class TaskQueueError(RuntimeError):
    """Базовая ошибка управления очередью задач."""


class TaskAlreadyRunningError(TaskQueueError):
    """У пользователя уже выполняется тяжёлая задача."""


@dataclass
class TaskCooldownError(TaskQueueError):
    """Слишком частый запуск одной и той же операции."""

    retry_after_seconds: int


class GlobalTaskLimitError(TaskQueueError):
    """Достигнут глобальный лимит тяжёлых задач."""


class TaskQueueService:
    """Асинхронные операции очереди (из процесса бота)."""

    async def enqueue(self, user_id: int, operation: str, payload: dict[str, Any]) -> UserTask:
        sf = get_session_factory()
        now = datetime.now(UTC)
        async with sf() as session:
            global_active = await session.scalar(
                select(func.count(UserTask.task_id)).where(
                    UserTask.status.in_(ACTIVE_TASK_STATUSES)
                )
            )
            if (global_active or 0) >= HEAVY_TASK_GLOBAL_LIMIT:
                raise GlobalTaskLimitError("Системный лимит фоновых задач достигнут")

            user_active = await session.scalar(
                select(UserTask.task_id).where(
                    UserTask.user_id == user_id,
                    UserTask.status.in_(ACTIVE_TASK_STATUSES),
                )
            )
            if user_active:
                raise TaskAlreadyRunningError("Для пользователя уже есть активная задача")

            last_same = await session.scalar(
                select(UserTask)
                .where(UserTask.user_id == user_id, UserTask.operation == operation)
                .order_by(desc(UserTask.created_at))
                .limit(1)
            )
            if (
                last_same is not None
                and last_same.cooldown_until is not None
                and last_same.cooldown_until > now
            ):
                retry_after = int((last_same.cooldown_until - now).total_seconds())
                raise TaskCooldownError(retry_after_seconds=max(1, retry_after))

            task = UserTask(
                task_id=uuid.uuid4().hex,
                user_id=user_id,
                operation=operation,
                status=TASK_STATUS_QUEUED,
                payload=payload,
                cooldown_until=now + timedelta(seconds=HEAVY_TASK_COOLDOWN_SECONDS),
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def attach_celery_id(self, task_id: str, celery_task_id: str) -> None:
        sf = get_session_factory()
        async with sf() as session:
            task = await session.get(UserTask, task_id)
            if task is None:
                return
            task.celery_task_id = celery_task_id
            await session.commit()

    async def get_user_task(self, user_id: int, task_id: str | None = None) -> UserTask | None:
        sf = get_session_factory()
        async with sf() as session:
            if task_id:
                task = await session.get(UserTask, task_id)
                if task and task.user_id == user_id:
                    return task
                return None
            return await session.scalar(
                select(UserTask)
                .where(UserTask.user_id == user_id)
                .order_by(desc(UserTask.created_at))
                .limit(1)
            )

    async def request_cancel(self, user_id: int, task_id: str | None = None) -> UserTask | None:
        sf = get_session_factory()
        async with sf() as session:
            if task_id:
                task = await session.get(UserTask, task_id)
                if task is None or task.user_id != user_id:
                    return None
            else:
                task = await session.scalar(
                    select(UserTask)
                    .where(
                        UserTask.user_id == user_id,
                        UserTask.status.in_(ACTIVE_TASK_STATUSES),
                    )
                    .order_by(desc(UserTask.created_at))
                    .limit(1)
                )
                if task is None:
                    return None
            task.cancel_requested = True
            if task.status == TASK_STATUS_QUEUED:
                task.status = TASK_STATUS_CANCELLED
                task.finished_at = datetime.now(UTC)
            else:
                task.status = TASK_STATUS_CANCEL_REQUESTED
            await session.commit()
            await session.refresh(task)
            return task


def _to_sync_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://")


class SyncTaskStore:
    """Синхронные операции очереди (из процесса Celery worker)."""

    def __init__(self, dsn: str | None = None) -> None:
        final_dsn = _to_sync_dsn(dsn or DATABASE_URL)
        self._engine = create_engine(final_dsn, future=True)
        self._session_factory = sessionmaker(bind=self._engine, class_=Session)

    def get_task(self, task_id: str) -> UserTask | None:
        with self._session_factory() as session:
            return session.get(UserTask, task_id)

    def mark_running(self, task_id: str) -> None:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return
            task.status = TASK_STATUS_RUNNING
            task.started_at = datetime.now(UTC)
            session.commit()

    def set_progress(self, task_id: str, text: str) -> None:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return
            task.progress = text[:4000]
            session.commit()

    def is_cancel_requested(self, task_id: str) -> bool:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return False
            return bool(task.cancel_requested)

    def mark_success(self, task_id: str, result_text: str = "") -> None:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return
            task.status = TASK_STATUS_SUCCESS
            task.result_text = result_text[:4000]
            task.finished_at = datetime.now(UTC)
            session.commit()

    def mark_cancelled(self, task_id: str, result_text: str = "") -> None:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return
            task.status = TASK_STATUS_CANCELLED
            task.result_text = result_text[:4000]
            task.finished_at = datetime.now(UTC)
            session.commit()

    def mark_failed(self, task_id: str, error_text: str) -> None:
        with self._session_factory() as session:
            task = session.get(UserTask, task_id)
            if task is None:
                return
            task.status = TASK_STATUS_FAILED
            task.error_text = error_text[:4000]
            task.finished_at = datetime.now(UTC)
            session.commit()
