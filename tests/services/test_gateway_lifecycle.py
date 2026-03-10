from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bot.services.api import ApiService


class _FakeStorage:
    def get_config_backend(self, user_id: int) -> Any:
        raise NotImplementedError

    def get_cookie_backend(self, user_id: int) -> Any:
        raise NotImplementedError

    def get_work_dir(self, user_id: int) -> Path:
        return Path(".")


class _FakeGateway:
    def __init__(self) -> None:
        self.closed = 0

    async def call_api(self, method: str, endpoint: str, params=None, delay=None) -> dict[str, Any]:
        return {"ok": True}

    async def aclose(self) -> None:
        self.closed += 1


class _FailingGateway(_FakeGateway):
    async def call_api(self, method: str, endpoint: str, params=None, delay=None) -> dict[str, Any]:
        raise RuntimeError("boom")


def test_gateway_closed_on_success_and_error_paths() -> None:
    async def scenario() -> None:
        storage = _FakeStorage()
        service = ApiService(storage=storage)

        success_gateway = _FakeGateway()
        service._get_gateway = lambda user_id: success_gateway  # type: ignore[method-assign]
        await service.call_api(user_id=1, method="GET", endpoint="/ok")
        assert success_gateway.closed == 1

        failing_gateway = _FailingGateway()
        service._get_gateway = lambda user_id: failing_gateway  # type: ignore[method-assign]
        try:
            await service.call_api(user_id=1, method="GET", endpoint="/fail")
        except RuntimeError:
            pass
        assert failing_gateway.closed == 1

    asyncio.run(scenario())
