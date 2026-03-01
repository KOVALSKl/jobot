"""Настройки хранилища данных и фабрика коннекторов."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "filesystem")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))


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
