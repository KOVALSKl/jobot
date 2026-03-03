"""Синхронные backends hh-applicant-tool поверх PostgreSQL."""

from __future__ import annotations

import json
import tempfile
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from bot.security.crypto import CryptoService


def _to_sync_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def _is_encrypted_payload(data: dict[str, Any]) -> bool:
    return "ciphertext" in data and "enc_version" in data


class PgSyncConfigBackend:
    """ConfigBackend через sync SQLAlchemy engine."""

    def __init__(self, engine: Engine, user_id: int, crypto: CryptoService) -> None:
        self._engine = engine
        self._user_id = user_id
        self._crypto = crypto
        self._lock = Lock()

    def exists(self) -> bool:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM user_config WHERE user_id=:uid"),
                {"uid": self._user_id},
            ).first()
            return row is not None

    def load(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT config_data FROM user_config WHERE user_id=:uid"),
                {"uid": self._user_id},
            ).first()
            if row is None:
                return {}
            payload = row[0] or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            if _is_encrypted_payload(payload):
                return self._crypto.decrypt_json(payload)
            return dict(payload)

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            current = self.load()
            current.update(data)
            encrypted_payload = self._crypto.encrypt_json(current)
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO user_config (user_id, config_data, enc_version)
                        VALUES (:uid, CAST(:payload AS jsonb), :enc)
                        ON CONFLICT (user_id) DO UPDATE
                        SET config_data=CAST(:payload AS jsonb), enc_version=:enc, updated_at=now()
                        """
                    ),
                    {
                        "uid": self._user_id,
                        "payload": json.dumps(encrypted_payload, ensure_ascii=False),
                        "enc": self._crypto.ENC_VERSION,
                    },
                )


class PgSyncCookieBackend:
    """CookieBackend через sync SQLAlchemy engine."""

    def __init__(self, engine: Engine, user_id: int, crypto: CryptoService) -> None:
        self._engine = engine
        self._user_id = user_id
        self._crypto = crypto

    def exists(self) -> bool:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM user_cookies WHERE user_id=:uid"),
                {"uid": self._user_id},
            ).first()
            return row is not None

    def load_to_jar(self, jar: MozillaCookieJar) -> None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT cookies_text, enc_version FROM user_cookies WHERE user_id=:uid"),
                {"uid": self._user_id},
            ).first()
            if row is None:
                return
            cookies_text = row[0] or ""
            enc_version = int(row[1] or 0)
            if enc_version >= 1:
                cookies_text = self._crypto.decrypt_text(cookies_text)
            if not cookies_text:
                return
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            )
            try:
                tmp.write(cookies_text)
                tmp.close()
                jar.filename = tmp.name
                jar.load(ignore_discard=True, ignore_expires=True)
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    def save_from_text(self, text_value: str) -> None:
        encrypted_text = self._crypto.encrypt_text(text_value)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO user_cookies (user_id, cookies_text, enc_version)
                    VALUES (:uid, :cookies, :enc)
                    ON CONFLICT (user_id) DO UPDATE
                    SET cookies_text=:cookies, enc_version=:enc, updated_at=now()
                    """
                ),
                {
                    "uid": self._user_id,
                    "cookies": encrypted_text,
                    "enc": self._crypto.ENC_VERSION,
                },
            )


def build_sync_engine(dsn: str) -> Engine:
    """Создаёт sync engine для worker/sync-backend слоя."""
    return create_engine(_to_sync_dsn(dsn), future=True, pool_pre_ping=True)
