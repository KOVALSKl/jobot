from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bot.services.auth import AuthService


class FakeStorage:
    def __init__(self) -> None:
        self._config: dict[int, dict[str, Any]] = {}
        self._cookies: dict[int, str] = {}

    async def config_exists(self, user_id: int) -> bool:
        return user_id in self._config

    async def load_config(self, user_id: int) -> dict[str, Any]:
        return dict(self._config.get(user_id, {}))

    async def save_config(self, user_id: int, data: dict[str, Any]) -> None:
        current = dict(self._config.get(user_id, {}))
        current.update(data)
        self._config[user_id] = current

    async def delete_config_key(self, user_id: int, key: str) -> None:
        current = dict(self._config.get(user_id, {}))
        current.pop(key, None)
        self._config[user_id] = current

    async def load_cookies(self, user_id: int) -> str | None:
        return self._cookies.get(user_id)

    async def save_cookies(self, user_id: int, cookies_text: str) -> None:
        self._cookies[user_id] = cookies_text

    def get_config_backend(self, user_id: int):  # pragma: no cover - not used
        raise NotImplementedError

    def get_cookie_backend(self, user_id: int):  # pragma: no cover - not used
        raise NotImplementedError

    def get_work_dir(self, user_id: int) -> Path:
        return Path(".")

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None


def test_auth_service_async_flow() -> None:
    async def scenario() -> None:
        storage = FakeStorage()
        auth = AuthService(storage=storage)
        user_id = 777

        assert not await auth.is_authenticated(user_id)

        await auth.save_tokens(
            user_id=user_id,
            access_token="access",
            refresh_token="refresh",
            expires_at=123456,
        )
        assert await auth.is_authenticated(user_id)

        await auth.logout(user_id)
        assert not await auth.is_authenticated(user_id)

    asyncio.run(scenario())

