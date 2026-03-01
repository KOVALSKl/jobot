"""Утилиты чтения секретов из Docker secrets и env."""

from __future__ import annotations

import os
from pathlib import Path

_SECRETS_DIR = Path("/run/secrets")


def read_secret_file(name: str) -> str | None:
    """Читает секрет из файла /run/secrets/<name>."""
    path = _SECRETS_DIR / name
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def get_secret(name: str, env_name: str | None = None, default: str = "") -> str:
    """Возвращает секрет из файла, env или default."""
    if secret := read_secret_file(name):
        return secret
    if env_name and (value := os.getenv(env_name)):
        return value
    return default


def require_secret(name: str, env_name: str | None = None) -> str:
    """Возвращает обязательный секрет или бросает ValueError."""
    value = get_secret(name=name, env_name=env_name, default="")
    if not value:
        origin = f"/run/secrets/{name}" + (f" или {env_name}" if env_name else "")
        raise ValueError(f"Обязательный секрет не найден: {origin}")
    return value
