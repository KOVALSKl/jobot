"""Файловый коннектор хранилища — поведение по умолчанию."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from hh_applicant_tool.backends import (
    ConfigBackend,
    CookieBackend,
    FileConfigBackend,
    FileCookieBackend,
)


class FileSystemStorage:
    """Хранение данных в файловой системе (data/{user_id}/).

    Полностью совместим с текущей структурой хранения:
      data/{user_id}/config.json — токены и настройки
      data/{user_id}/cookies.txt — cookies в формате Netscape
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._config_locks: dict[int, asyncio.Lock] = {}
        self._cookies_locks: dict[int, asyncio.Lock] = {}

    def _get_config_lock(self, user_id: int) -> asyncio.Lock:
        lock = self._config_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._config_locks[user_id] = lock
        return lock

    def _get_cookies_lock(self, user_id: int) -> asyncio.Lock:
        lock = self._cookies_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._cookies_locks[user_id] = lock
        return lock

    # ── Config ───────────────────────────────────────────

    def _config_backend(self, user_id: int) -> FileConfigBackend:
        return FileConfigBackend(self._data_dir / str(user_id) / "config.json")

    async def config_exists(self, user_id: int) -> bool:
        return await asyncio.to_thread(self._config_backend(user_id).exists)

    async def load_config(self, user_id: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._config_backend(user_id).load)

    async def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        async with self._get_config_lock(user_id):
            backend = self._config_backend(user_id)
            existing = await asyncio.to_thread(backend.load) if await asyncio.to_thread(backend.exists) else {}
            existing.update(data)
            await asyncio.to_thread(backend.save, existing)

    async def delete_config_key(self, user_id: int, key: str) -> None:
        async with self._get_config_lock(user_id):
            backend = self._config_backend(user_id)
            if not await asyncio.to_thread(backend.exists):
                return
            cfg = await asyncio.to_thread(backend.load)
            cfg.pop(key, None)
            await asyncio.to_thread(backend.save, cfg)

    # ── Cookies ──────────────────────────────────────────

    def _cookie_backend(self, user_id: int) -> FileCookieBackend:
        return FileCookieBackend(self._data_dir / str(user_id) / "cookies.txt")

    async def load_cookies(self, user_id: int) -> str | None:
        async with self._get_cookies_lock(user_id):
            path = self._data_dir / str(user_id) / "cookies.txt"
            exists = await asyncio.to_thread(path.exists)
            if not exists:
                return None
            return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def save_cookies(self, user_id: int, cookies_text: str) -> None:
        async with self._get_cookies_lock(user_id):
            await asyncio.to_thread(self._cookie_backend(user_id).save_from_text, cookies_text)

    # ── Бэкенды для hh-applicant-tool ────────────────────

    def get_config_backend(self, user_id: int) -> ConfigBackend:
        return self._config_backend(user_id)

    def get_cookie_backend(self, user_id: int) -> CookieBackend:
        return self._cookie_backend(user_id)

    def get_work_dir(self, user_id: int) -> Path:
        work_dir = self._data_dir / str(user_id)
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    # ── Lifecycle ────────────────────────────────────────

    async def init(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        pass
