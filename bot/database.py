"""Управление async-подключением к PostgreSQL через SQLAlchemy."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(dsn: str) -> None:
    """Создаёт async engine и фабрику сессий."""
    global engine, async_session_factory
    engine = create_async_engine(dsn, echo=False)
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def close_db() -> None:
    """Закрывает пул соединений."""
    global engine, async_session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику сессий. Вызывать после init_db()."""
    if async_session_factory is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db() сначала.")
    return async_session_factory
