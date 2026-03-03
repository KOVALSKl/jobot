"""Конфигурация Celery для фоновых тяжёлых задач."""

from __future__ import annotations

from typing import Any, Callable

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - fallback для локального тестового окружения
    class _DummyControl:
        def revoke(self, task_id: str, terminate: bool = False) -> None:
            return None

    class Celery:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.conf = {}
            self.control = _DummyControl()

        def task(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

        def send_task(self, *args: Any, **kwargs: Any):
            class _Result:
                id = kwargs.get("task_id", "inline")

            return _Result()

from bot.settings import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "hh_bot",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["bot.worker_tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_track_started=True,
    task_time_limit=60 * 60,
    task_soft_time_limit=55 * 60,
    broker_connection_retry_on_startup=True,
)
