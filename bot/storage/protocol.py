"""Протокол коннектора хранилища данных."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from hh_applicant_tool.backends import ConfigBackend, CookieBackend


@runtime_checkable
class StorageConnector(Protocol):
    """Единый интерфейс доступа к хранилищу данных пользователей.

    Реализации определяют конкретный способ хранения:
    файловая система, PostgreSQL и т.д.
    """

    # ── Config (токены + настройки) ──────────────────────

    async def config_exists(self, user_id: int) -> bool:
        """Проверяет наличие конфигурации для пользователя."""
        ...

    async def load_config(self, user_id: int) -> dict[str, Any]:
        """Загружает конфигурацию пользователя как dict."""
        ...

    async def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        """Сохраняет конфигурацию (merge с существующей)."""
        ...

    async def delete_config_key(self, user_id: int, key: str) -> None:
        """Удаляет ключ из конфигурации пользователя."""
        ...

    # ── Cookies ──────────────────────────────────────────

    async def load_cookies(self, user_id: int) -> str | None:
        """Загружает cookies в формате Netscape. None если нет."""
        ...

    async def save_cookies(self, user_id: int, cookies_text: str) -> None:
        """Сохраняет cookies в формате Netscape."""
        ...

    # ── Бэкенды для hh-applicant-tool ────────────────────

    def get_config_backend(self, user_id: int) -> ConfigBackend:
        """Возвращает ConfigBackend для HHApplicantTool."""
        ...

    def get_cookie_backend(self, user_id: int) -> CookieBackend:
        """Возвращает CookieBackend для HHApplicantTool."""
        ...

    def get_work_dir(self, user_id: int) -> Path:
        """Рабочая директория для логов и SQLite hh-applicant-tool."""
        ...

    # ── Lifecycle ────────────────────────────────────────

    async def init(self) -> None:
        """Инициализация коннектора (подключение к БД, создание директорий)."""
        ...

    async def close(self) -> None:
        """Закрытие соединений и освобождение ресурсов."""
        ...
