from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

from bot.services.hh_gateway_async import AsyncHHGateway
from hh_applicant_tool.main import HHApplicantTool


class _FakeSyncApiClient:
    def __init__(self) -> None:
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.access_expires_at: int = 0

    def handle_access_token(self, token: dict[str, Any]) -> None:
        self.access_token = token.get("access_token")
        self.refresh_token = token.get("refresh_token")
        self.access_expires_at = token.get("access_expires_at", 0)


class _FakeOAuthClient:
    async def authenticate(self, code: str) -> dict[str, Any]:
        assert code == "auth-code"
        return {
            "access_token": "USER_EXCHANGED",
            "refresh_token": "REFRESH_EXCHANGED",
            "access_expires_at": int(time.time()) + 600,
        }


class _FakeAsyncApiClient:
    def __init__(self) -> None:
        self.access_token = "USER_OLD"
        self.refresh_token = "REFRESH_OLD"
        self.access_expires_at = 0
        self.oauth_client = _FakeOAuthClient()

    @property
    def is_access_expired(self) -> bool:
        return time.time() >= self.access_expires_at

    def handle_access_token(self, token: dict[str, Any]) -> None:
        self.access_token = token.get("access_token")
        self.refresh_token = token.get("refresh_token")
        self.access_expires_at = token.get("access_expires_at", 0)

    async def refresh_access_token(self) -> None:
        self.handle_access_token({
            "access_token": "USER_REFRESHED",
            "refresh_token": "REFRESH_REFRESHED",
            "access_expires_at": int(time.time()) + 900,
        })


class _FakeTool:
    def __init__(self) -> None:
        self.api_client = _FakeSyncApiClient()
        self.async_api_client = _FakeAsyncApiClient()
        self.saved_tokens: list[dict[str, Any]] = []

    async def asave_token(self) -> bool:
        self.saved_tokens.append({
            "access_token": self.async_api_client.access_token,
            "refresh_token": self.async_api_client.refresh_token,
            "access_expires_at": self.async_api_client.access_expires_at,
        })
        return True

    async def arefresh_access_token(self) -> None:
        await self.async_api_client.refresh_access_token()

    async def aclose(self) -> None:
        return None


def test_async_client_uses_client_secret_from_config() -> None:
    tool = HHApplicantTool.__new__(HHApplicantTool)
    tool.args = SimpleNamespace(api_delay=None, user_agent=None)
    tool.config = {
        "client_id": "CID-123",
        "client_secret": "SECRET-456",
        "token": {
            "access_token": "USER_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "access_expires_at": int(time.time()) + 3600,
        },
    }

    assert tool.async_api_client.client_id == "CID-123"
    assert tool.async_api_client.client_secret == "SECRET-456"


def test_async_gateway_exchange_and_refresh_work_on_mocks() -> None:
    async def scenario() -> None:
        tool = _FakeTool()
        gateway = AsyncHHGateway(user_id=1, tool=tool)
        exchanged = await gateway.exchange_code("auth-code")
        assert exchanged["access_token"] == "USER_EXCHANGED"
        assert tool.async_api_client.access_token == "USER_EXCHANGED"
        assert tool.api_client.access_token == "USER_EXCHANGED"
        tool.async_api_client.access_expires_at = 0
        refreshed = await gateway.refresh_token_if_needed()
        assert refreshed is True
        assert tool.async_api_client.access_token == "USER_REFRESHED"
        assert tool.saved_tokens[-1]["access_token"] == "USER_REFRESHED"

        await gateway.aclose()

    asyncio.run(scenario())
