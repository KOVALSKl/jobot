from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from hh_applicant_tool.api.async_client import AsyncApiClient


class _FakeAsyncClient:
    def __init__(self, call_timestamps: list[float]) -> None:
        self._call_timestamps = call_timestamps

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._call_timestamps.append(time.monotonic())
        await asyncio.sleep(0.001)
        req = httpx.Request(method=method, url=url)
        return httpx.Response(status_code=200, json={"ok": True}, request=req)

    async def aclose(self) -> None:
        return None


def test_async_api_client_rate_limit_no_parallel_burst() -> None:
    async def scenario() -> None:
        timestamps: list[float] = []
        delay = 0.05
        client = AsyncApiClient(
            access_token="USER_TEST_TOKEN",
            delay=delay,
            client=_FakeAsyncClient(timestamps),
            max_retries=0,
            base_url="https://example.com/",
        )
        await asyncio.gather(
            client.get("/test"),
            client.post("/test", {"a": 1}),
            client.get("/test"),
            client.post("/test", {"b": 2}),
            client.get("/test"),
        )
        await client.aclose()

        assert len(timestamps) == 5
        gaps = [
            timestamps[idx + 1] - timestamps[idx]
            for idx in range(len(timestamps) - 1)
        ]
        assert min(gaps) >= delay * 0.9

    asyncio.run(scenario())
