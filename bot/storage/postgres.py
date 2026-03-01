"""PostgreSQL коннектор хранилища данных."""

from __future__ import annotations

import io
import tempfile
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hh_applicant_tool.backends import ConfigBackend, CookieBackend

from bot.database import close_db, get_session_factory, init_db
from bot.models import UserConfig, UserCookies


# ── Бэкенды для hh-applicant-tool (синхронные обёртки) ──────────────


class PgConfigBackend:
    """ConfigBackend поверх PostgreSQL (синхронный через asyncio.run)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], user_id: int) -> None:
        self._sf = session_factory
        self._user_id = user_id

    def _run(self, coro: Any) -> Any:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    def exists(self) -> bool:
        async def _check() -> bool:
            async with self._sf() as session:
                result = await session.get(UserConfig, self._user_id)
                return result is not None
        return self._run(_check())

    def load(self) -> dict[str, Any]:
        async def _load() -> dict[str, Any]:
            async with self._sf() as session:
                row = await session.get(UserConfig, self._user_id)
                if row is None:
                    return {}
                return dict(row.config_data)
        return self._run(_load())

    def save(self, data: dict[str, Any]) -> None:
        async def _save() -> None:
            async with self._sf() as session:
                stmt = pg_insert(UserConfig).values(
                    user_id=self._user_id,
                    config_data=data,
                ).on_conflict_do_update(
                    index_elements=[UserConfig.user_id],
                    set_={"config_data": data},
                )
                await session.execute(stmt)
                await session.commit()
        self._run(_save())


class PgCookieBackend:
    """CookieBackend поверх PostgreSQL (синхронный через asyncio.run)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], user_id: int) -> None:
        self._sf = session_factory
        self._user_id = user_id

    def _run(self, coro: Any) -> Any:
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    def exists(self) -> bool:
        async def _check() -> bool:
            async with self._sf() as session:
                row = await session.get(UserCookies, self._user_id)
                return row is not None
        return self._run(_check())

    def load_to_jar(self, jar: MozillaCookieJar) -> None:
        async def _load() -> str | None:
            async with self._sf() as session:
                row = await session.get(UserCookies, self._user_id)
                return row.cookies_text if row else None
        text = self._run(_load())
        if not text:
            return
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        try:
            tmp.write(text)
            tmp.close()
            jar.filename = tmp.name
            jar.load(ignore_discard=True, ignore_expires=True)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def save_from_text(self, text: str) -> None:
        async def _save() -> None:
            async with self._sf() as session:
                stmt = pg_insert(UserCookies).values(
                    user_id=self._user_id,
                    cookies_text=text,
                ).on_conflict_do_update(
                    index_elements=[UserCookies.user_id],
                    set_={"cookies_text": text},
                )
                await session.execute(stmt)
                await session.commit()
        self._run(_save())


# ── PostgreSQL Storage Connector ────────────────────────────────────


class PostgreSQLStorage:
    """Хранение данных пользователей в PostgreSQL.

    Конфигурация хранится как JSONB, cookies — как текст.
    """

    def __init__(self, dsn: str, work_dir: Path | None = None) -> None:
        self._dsn = dsn
        self._work_dir = work_dir or Path(tempfile.mkdtemp(prefix="hh-bot-"))

    # ── Config ───────────────────────────────────────────

    def config_exists(self, user_id: int) -> bool:
        return PgConfigBackend(get_session_factory(), user_id).exists()

    def load_config(self, user_id: int) -> dict[str, Any]:
        return PgConfigBackend(get_session_factory(), user_id).load()

    def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        backend = PgConfigBackend(get_session_factory(), user_id)
        existing = backend.load() if backend.exists() else {}
        existing.update(data)
        backend.save(existing)

    def delete_config_key(self, user_id: int, key: str) -> None:
        backend = PgConfigBackend(get_session_factory(), user_id)
        if not backend.exists():
            return
        cfg = backend.load()
        cfg.pop(key, None)
        backend.save(cfg)

    # ── Cookies ──────────────────────────────────────────

    def load_cookies(self, user_id: int) -> str | None:
        async def _load() -> str | None:
            sf = get_session_factory()
            async with sf() as session:
                row = await session.get(UserCookies, user_id)
                return row.cookies_text if row else None

        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_load())
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _load()).result()

    def save_cookies(self, user_id: int, cookies_text: str) -> None:
        PgCookieBackend(get_session_factory(), user_id).save_from_text(cookies_text)

    # ── Бэкенды для hh-applicant-tool ────────────────────

    def get_config_backend(self, user_id: int) -> ConfigBackend:
        return PgConfigBackend(get_session_factory(), user_id)

    def get_cookie_backend(self, user_id: int) -> CookieBackend:
        return PgCookieBackend(get_session_factory(), user_id)

    def get_work_dir(self, user_id: int) -> Path:
        work_dir = self._work_dir / str(user_id)
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    # ── Lifecycle ────────────────────────────────────────

    async def init(self) -> None:
        await init_db(self._dsn)
        self._work_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        await close_db()
