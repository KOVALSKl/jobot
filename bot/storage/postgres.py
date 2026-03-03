"""PostgreSQL коннектор хранилища данных."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hh_applicant_tool.backends import ConfigBackend, CookieBackend

from bot.database import close_db, get_session_factory, init_db
from bot.models import UserConfig, UserCookies
from bot.security.crypto import CryptoService, get_crypto_service
from bot.storage.postgres_sync_backends import (
    PgSyncConfigBackend,
    PgSyncCookieBackend,
    build_sync_engine,
)


class PostgreSQLStorage:
    """Хранение данных пользователей в PostgreSQL."""

    def __init__(self, dsn: str, work_dir: Path | None = None) -> None:
        self._dsn = dsn
        self._work_dir = work_dir or Path(tempfile.mkdtemp(prefix="hh-bot-"))
        self._crypto = get_crypto_service()
        self._sync_engine = build_sync_engine(dsn)

    @staticmethod
    def _is_encrypted_payload(data: dict[str, Any]) -> bool:
        return "ciphertext" in data and "enc_version" in data

    async def _load_raw_config(
        self, session: AsyncSession, user_id: int
    ) -> dict[str, Any] | None:
        row = await session.get(UserConfig, user_id)
        if row is None:
            return None
        payload = dict(row.config_data or {})
        if self._is_encrypted_payload(payload):
            return self._crypto.decrypt_json(payload)
        # Обратная совместимость с незашифрованными записями
        return payload

    async def config_exists(self, user_id: int) -> bool:
        sf = get_session_factory()
        async with sf() as session:
            return await session.get(UserConfig, user_id) is not None

    async def load_config(self, user_id: int) -> dict[str, Any]:
        sf = get_session_factory()
        async with sf() as session:
            config = await self._load_raw_config(session, user_id)
            return config or {}

    async def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        sf = get_session_factory()
        async with sf() as session:
            async with session.begin():
                row = await session.get(UserConfig, user_id, with_for_update=True)
                if row is None:
                    merged = dict(data)
                    encrypted_payload = self._crypto.encrypt_json(merged)
                    session.add(
                        UserConfig(
                            user_id=user_id,
                            config_data=encrypted_payload,
                            enc_version=self._crypto.ENC_VERSION,
                        )
                    )
                    return

                payload = dict(row.config_data or {})
                current = (
                    self._crypto.decrypt_json(payload)
                    if self._is_encrypted_payload(payload)
                    else payload
                )
                current.update(data)
                row.config_data = self._crypto.encrypt_json(current)
                row.enc_version = self._crypto.ENC_VERSION

    async def delete_config_key(self, user_id: int, key: str) -> None:
        sf = get_session_factory()
        async with sf() as session:
            async with session.begin():
                row = await session.get(UserConfig, user_id, with_for_update=True)
                if row is None:
                    return
                payload = dict(row.config_data or {})
                current = (
                    self._crypto.decrypt_json(payload)
                    if self._is_encrypted_payload(payload)
                    else payload
                )
                current.pop(key, None)
                row.config_data = self._crypto.encrypt_json(current)
                row.enc_version = self._crypto.ENC_VERSION

    async def load_cookies(self, user_id: int) -> str | None:
        sf = get_session_factory()
        async with sf() as session:
            row = await session.get(UserCookies, user_id)
            if row is None or not row.cookies_text:
                return None
            return (
                self._crypto.decrypt_text(row.cookies_text)
                if (row.enc_version or 0) >= 1
                else row.cookies_text
            )

    async def save_cookies(self, user_id: int, cookies_text: str) -> None:
        encrypted_text = self._crypto.encrypt_text(cookies_text)
        sf = get_session_factory()
        async with sf() as session:
            stmt = pg_insert(UserCookies).values(
                user_id=user_id,
                cookies_text=encrypted_text,
                enc_version=self._crypto.ENC_VERSION,
            ).on_conflict_do_update(
                index_elements=[UserCookies.user_id],
                set_={
                    "cookies_text": encrypted_text,
                    "enc_version": self._crypto.ENC_VERSION,
                },
            )
            await session.execute(stmt)
            await session.commit()

    def _config_backend(self, user_id: int) -> ConfigBackend:
        return PgSyncConfigBackend(
            engine=self._sync_engine, user_id=user_id, crypto=self._crypto
        )

    def _cookie_backend(self, user_id: int) -> CookieBackend:
        return PgSyncCookieBackend(
            engine=self._sync_engine, user_id=user_id, crypto=self._crypto
        )

    def get_config_backend(self, user_id: int) -> ConfigBackend:
        return self._config_backend(user_id)

    def get_cookie_backend(self, user_id: int) -> CookieBackend:
        return self._cookie_backend(user_id)

    def get_work_dir(self, user_id: int) -> Path:
        work_dir = self._work_dir / str(user_id)
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    async def init(self) -> None:
        await init_db(self._dsn)
        self._work_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        await close_db()
        self._sync_engine.dispose()
