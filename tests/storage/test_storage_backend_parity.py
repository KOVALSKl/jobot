from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from bot.models import Base
from bot.storage.filesystem import FileSystemStorage
from bot.storage.postgres import PostgreSQLStorage


async def _create_postgres_storage(tmp_path: Path) -> PostgreSQLStorage:
    dsn = os.getenv("TEST_POSTGRES_DSN", "")
    if not dsn:
        pytest.skip("TEST_POSTGRES_DSN не задан: postgres parity-тесты пропущены.")

    storage = PostgreSQLStorage(dsn=dsn, work_dir=tmp_path / "pg-workdir")
    await storage.init()

    # Тесты предполагают, что таблицы могут отсутствовать в чистой БД.
    from bot.database import engine

    if engine is None:
        raise RuntimeError("DB engine не инициализирован после storage.init().")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return storage


async def _make_storage(backend: str, tmp_path: Path):
    if backend == "filesystem":
        storage = FileSystemStorage(data_dir=tmp_path / "fs-data")
        await storage.init()
        return storage
    if backend == "postgres":
        return await _create_postgres_storage(tmp_path)
    raise ValueError(f"Unknown backend: {backend}")


@pytest.mark.parametrize("backend", ["filesystem", "postgres"])
def test_storage_backend_parity_core_flow(tmp_path: Path, backend: str) -> None:
    async def scenario() -> None:
        storage = await _make_storage(backend, tmp_path)
        try:
            user_id = int(time.time() * 1000) % 1_000_000_000

            assert not await storage.config_exists(user_id)

            await storage.save_config(user_id, {"token": {"access_token": "t1"}})
            await storage.save_config(user_id, {"meta": {"lang": "ru"}})
            cfg = await storage.load_config(user_id)
            assert cfg["token"]["access_token"] == "t1"
            assert cfg["meta"]["lang"] == "ru"

            await storage.delete_config_key(user_id, "token")
            cfg2 = await storage.load_config(user_id)
            assert "token" not in cfg2

            cookies = "# Netscape HTTP Cookie File\n.example\tTRUE\t/\tFALSE\t0\tsid\txyz\n"
            await storage.save_cookies(user_id, cookies)
            loaded_cookies = await storage.load_cookies(user_id)
            assert loaded_cookies == cookies
        finally:
            await storage.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["filesystem", "postgres"])
def test_storage_backend_parity_concurrent_merges(tmp_path: Path, backend: str) -> None:
    async def scenario() -> None:
        storage = await _make_storage(backend, tmp_path)
        try:
            user_id = int(time.time() * 1000) % 1_000_000_000 + 1
            await storage.save_config(user_id, {"root": 1})

            await asyncio.gather(
                *[
                    storage.save_config(user_id, {f"k{i}": i})
                    for i in range(20)
                ]
            )

            cfg = await storage.load_config(user_id)
            assert cfg["root"] == 1
            for i in range(20):
                assert cfg[f"k{i}"] == i
        finally:
            await storage.close()

    asyncio.run(scenario())

