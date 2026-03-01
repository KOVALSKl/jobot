"""PostgreSQL коннектор хранилища данных."""

from __future__ import annotations

import asyncio
import concurrent.futures
import tempfile
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hh_applicant_tool.backends import ConfigBackend, CookieBackend

from bot.database import close_db, get_session_factory, init_db
from bot.models import UserConfig, UserCookies
from bot.security.crypto import CryptoService, get_crypto_service


def _run_async(coro: Any) -> Any:
    """Выполняет async-корутины из синхронного кода."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class PgConfigBackend:
    """ConfigBackend поверх PostgreSQL."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        crypto: CryptoService,
        user_id: int,
    ) -> None:
        self._sf = session_factory
        self._crypto = crypto
        self._user_id = user_id

    @staticmethod
    def _is_encrypted_payload(data: dict[str, Any]) -> bool:
        return "ciphertext" in data and "enc_version" in data

    def exists(self) -> bool:
        async def _check() -> bool:
            async with self._sf() as session:
                return await session.get(UserConfig, self._user_id) is not None

        return bool(_run_async(_check()))

    def load(self) -> dict[str, Any]:
        async def _load() -> dict[str, Any]:
            async with self._sf() as session:
                row = await session.get(UserConfig, self._user_id)
                if row is None:
                    return {}
                payload = dict(row.config_data or {})
                if self._is_encrypted_payload(payload):
                    return self._crypto.decrypt_json(payload)
                # Обратная совместимость с незашифрованными записями
                return payload

        return _run_async(_load())

    def save(self, data: dict[str, Any]) -> None:
        async def _save() -> None:
            encrypted_payload = self._crypto.encrypt_json(data)
            async with self._sf() as session:
                stmt = pg_insert(UserConfig).values(
                    user_id=self._user_id,
                    config_data=encrypted_payload,
                    enc_version=self._crypto.ENC_VERSION,
                ).on_conflict_do_update(
                    index_elements=[UserConfig.user_id],
                    set_={
                        "config_data": encrypted_payload,
                        "enc_version": self._crypto.ENC_VERSION,
                    },
                )
                await session.execute(stmt)
                await session.commit()

        _run_async(_save())


class PgCookieBackend:
    """CookieBackend поверх PostgreSQL."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        crypto: CryptoService,
        user_id: int,
    ) -> None:
        self._sf = session_factory
        self._crypto = crypto
        self._user_id = user_id

    def exists(self) -> bool:
        async def _check() -> bool:
            async with self._sf() as session:
                return await session.get(UserCookies, self._user_id) is not None

        return bool(_run_async(_check()))

    def load_to_jar(self, jar: MozillaCookieJar) -> None:
        async def _load() -> tuple[str | None, int | None]:
            async with self._sf() as session:
                row = await session.get(UserCookies, self._user_id)
                if row is None:
                    return None, None
                return row.cookies_text, row.enc_version

        raw_text, enc_version = _run_async(_load())
        if not raw_text:
            return

        cookies_text = (
            self._crypto.decrypt_text(raw_text)
            if (enc_version or 0) >= 1
            else raw_text
        )
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

    def save_from_text(self, text: str) -> None:
        async def _save() -> None:
            encrypted_text = self._crypto.encrypt_text(text)
            async with self._sf() as session:
                stmt = pg_insert(UserCookies).values(
                    user_id=self._user_id,
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

        _run_async(_save())


class PostgreSQLStorage:
    """Хранение данных пользователей в PostgreSQL."""

    def __init__(self, dsn: str, work_dir: Path | None = None) -> None:
        self._dsn = dsn
        self._work_dir = work_dir or Path(tempfile.mkdtemp(prefix="hh-bot-"))
        self._crypto = get_crypto_service()

    def _config_backend(self, user_id: int) -> PgConfigBackend:
        return PgConfigBackend(get_session_factory(), self._crypto, user_id)

    def _cookie_backend(self, user_id: int) -> PgCookieBackend:
        return PgCookieBackend(get_session_factory(), self._crypto, user_id)

    def config_exists(self, user_id: int) -> bool:
        return self._config_backend(user_id).exists()

    def load_config(self, user_id: int) -> dict[str, Any]:
        return self._config_backend(user_id).load()

    def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        backend = self._config_backend(user_id)
        current = backend.load() if backend.exists() else {}
        current.update(data)
        backend.save(current)

    def delete_config_key(self, user_id: int, key: str) -> None:
        backend = self._config_backend(user_id)
        if not backend.exists():
            return
        cfg = backend.load()
        cfg.pop(key, None)
        backend.save(cfg)

    def load_cookies(self, user_id: int) -> str | None:
        async def _load() -> tuple[str | None, int | None]:
            sf = get_session_factory()
            async with sf() as session:
                row = await session.get(UserCookies, user_id)
                if row is None:
                    return None, None
                return row.cookies_text, row.enc_version

        cookies_text, enc_version = _run_async(_load())
        if not cookies_text:
            return None
        return (
            self._crypto.decrypt_text(cookies_text)
            if (enc_version or 0) >= 1
            else cookies_text
        )

    def save_cookies(self, user_id: int, cookies_text: str) -> None:
        self._cookie_backend(user_id).save_from_text(cookies_text)

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
