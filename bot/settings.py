"""Настройки хранилища данных и фабрика коннекторов."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from bot.security.secrets import get_secret

load_dotenv()

STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "filesystem")
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "5432")
DB_NAME: str = os.getenv("DB_NAME", "hh_bot")
DB_USER: str = os.getenv("DB_USER", "hh_bot")
HEAVY_TASKS_MODE: str = os.getenv("HEAVY_TASKS_MODE", "inline")
HEAVY_TASK_COOLDOWN_SECONDS: int = int(
    os.getenv("HEAVY_TASK_COOLDOWN_SECONDS", "60")
)
HEAVY_TASK_GLOBAL_LIMIT: int = int(os.getenv("HEAVY_TASK_GLOBAL_LIMIT", "4"))
HH_GATEWAY_MODE: str = os.getenv("HH_GATEWAY_MODE", "async")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND: str = os.getenv(
    "CELERY_RESULT_BACKEND", "redis://redis:6379/1"
)


def _build_database_url() -> str:
    """Собирает DATABASE_URL из env или DB_* + secret с паролем."""
    explicit_url = os.getenv("DATABASE_URL", "")
    if explicit_url:
        return explicit_url
    password = get_secret("postgres_password", env_name="DB_PASSWORD")
    if not password:
        return ""
    escaped = quote_plus(password)
    return f"postgresql+asyncpg://{DB_USER}:{escaped}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


DATABASE_URL: str = _build_database_url()


def create_storage() -> "StorageConnector":
    """Создаёт коннектор хранилища в зависимости от STORAGE_BACKEND."""
    from bot.storage.protocol import StorageConnector

    if STORAGE_BACKEND == "postgres":
        if not DATABASE_URL:
            raise ValueError(
                "STORAGE_BACKEND=postgres, но DATABASE_URL не задан."
            )
        from bot.storage.postgres import PostgreSQLStorage
        return PostgreSQLStorage(dsn=DATABASE_URL, work_dir=DATA_DIR)

    from bot.storage.filesystem import FileSystemStorage
    return FileSystemStorage(data_dir=DATA_DIR)
