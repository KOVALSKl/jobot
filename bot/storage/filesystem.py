"""Файловый коннектор хранилища — поведение по умолчанию."""

from __future__ import annotations

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

    # ── Config ───────────────────────────────────────────

    def _config_backend(self, user_id: int) -> FileConfigBackend:
        return FileConfigBackend(self._data_dir / str(user_id) / "config.json")

    def config_exists(self, user_id: int) -> bool:
        return self._config_backend(user_id).exists()

    def load_config(self, user_id: int) -> dict[str, Any]:
        return self._config_backend(user_id).load()

    def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        backend = self._config_backend(user_id)
        existing = backend.load() if backend.exists() else {}
        existing.update(data)
        backend.save(existing)

    def delete_config_key(self, user_id: int, key: str) -> None:
        backend = self._config_backend(user_id)
        if not backend.exists():
            return
        cfg = backend.load()
        cfg.pop(key, None)
        backend.save(cfg)

    # ── Cookies ──────────────────────────────────────────

    def _cookie_backend(self, user_id: int) -> FileCookieBackend:
        return FileCookieBackend(self._data_dir / str(user_id) / "cookies.txt")

    def load_cookies(self, user_id: int) -> str | None:
        path = self._data_dir / str(user_id) / "cookies.txt"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_cookies(self, user_id: int, cookies_text: str) -> None:
        self._cookie_backend(user_id).save_from_text(cookies_text)

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
