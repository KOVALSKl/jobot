from __future__ import annotations

import asyncio

from bot.storage.filesystem import FileSystemStorage


def test_filesystem_storage_config_roundtrip(tmp_path) -> None:
    async def scenario() -> None:
        storage = FileSystemStorage(data_dir=tmp_path / "data")
        await storage.init()

        user_id = 101
        assert not await storage.config_exists(user_id)

        await storage.save_config(user_id, {"token": {"access_token": "abc"}})
        await storage.save_config(user_id, {"profile": {"name": "Bob"}})
        cfg = await storage.load_config(user_id)

        assert await storage.config_exists(user_id)
        assert cfg["token"]["access_token"] == "abc"
        assert cfg["profile"]["name"] == "Bob"

        await storage.delete_config_key(user_id, "token")
        cfg_after_delete = await storage.load_config(user_id)
        assert "token" not in cfg_after_delete

        await storage.close()

    asyncio.run(scenario())


def test_filesystem_storage_cookies_roundtrip(tmp_path) -> None:
    async def scenario() -> None:
        storage = FileSystemStorage(data_dir=tmp_path / "data")
        await storage.init()
        user_id = 202

        assert await storage.load_cookies(user_id) is None
        payload = "# Netscape HTTP Cookie File\n.example\tTRUE\t/\tFALSE\t0\tsid\t123\n"
        await storage.save_cookies(user_id, payload)
        loaded = await storage.load_cookies(user_id)
        assert loaded == payload

        await storage.close()

    asyncio.run(scenario())


def test_filesystem_storage_concurrent_config_updates(tmp_path) -> None:
    async def scenario() -> None:
        storage = FileSystemStorage(data_dir=tmp_path / "data")
        await storage.init()
        user_id = 303

        await storage.save_config(user_id, {"base": True})

        await asyncio.gather(
            *[
                storage.save_config(user_id, {f"key_{i}": i})
                for i in range(30)
            ]
        )

        cfg = await storage.load_config(user_id)
        assert cfg["base"] is True
        for i in range(30):
            assert cfg[f"key_{i}"] == i

        await storage.close()

    asyncio.run(scenario())

