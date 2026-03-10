"""Sync fallback gateway с изоляцией bridge-вызовов."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from hh_applicant_tool import HHApplicantTool

from bot.services.hh_gateway import GatewayInstrumentationMixin

_executor = ThreadPoolExecutor(max_workers=4)


class SyncHHGateway(GatewayInstrumentationMixin):
    """Fallback-адаптер sync HHApplicantTool с async интерфейсом.

    Нужен для совместимости: сервисы всегда работают с async контрактом
    gateway, а sync-вызовы изолируются в thread pool.
    """

    def __init__(self, user_id: int, tool: HHApplicantTool) -> None:
        super().__init__(user_id=user_id)
        self._tool = tool

    async def _call(self, operation: str, fn, *args: Any, **kwargs: Any) -> Any:
        async def _wrapped() -> Any:
            loop = asyncio.get_running_loop()
            # Любой блокирующий sync I/O уводим из event loop, чтобы не
            # деградировать latency остальных async-операций бота.
            return await loop.run_in_executor(
                _executor,
                partial(fn, *args, **kwargs),
            )

        return await self._observe(operation, _wrapped)

    def get_oauth_url(self) -> str:
        return self._tool.api_client.oauth_client.authorize_url

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Обменивает OAuth code и синхронизирует токен в sync-клиенте."""
        token = await self._call("oauth.authenticate", self._tool.api_client.oauth_client.authenticate, code)
        self._tool.api_client.handle_access_token(token)
        await self._call("tool.save_token", self._tool.save_token)
        return token

    async def get_me(self) -> dict[str, Any]:
        return await self._call("get_me", self._tool.get_me)

    async def get_resumes(self) -> list[dict[str, Any]]:
        return await self._call("get_resumes", self._tool.get_resumes)

    async def get_negotiations(self, status: str = "active") -> list[dict[str, Any]]:
        return await self._call("get_negotiations", lambda: list(self._tool.get_negotiations(status=status)))

    async def get_blacklisted(self) -> list[str]:
        return await self._call("get_blacklisted", self._tool.get_blacklisted)

    async def get_negotiation_messages(self, negotiation_id: str) -> dict[str, Any]:
        return await self._call(
            "get_negotiation_messages",
            self._tool.api_client.get,
            f"/negotiations/{negotiation_id}/messages",
        )

    async def create_negotiation(
        self,
        resume_id: str,
        vacancy_id: str,
        message: str,
        delay: float | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "create_negotiation",
            self._tool.api_client.post,
            "/negotiations",
            {
                "resume_id": resume_id,
                "vacancy_id": vacancy_id,
                "message": message,
            },
            delay=delay,
        )

    async def delete_negotiation(self, negotiation_id: str) -> dict[str, Any]:
        return await self._call(
            "delete_negotiation",
            self._tool.api_client.delete,
            f"/negotiations/active/{negotiation_id}",
            {"with_decline_message": True},
        )

    async def blacklist_employer(self, employer_id: str) -> dict[str, Any]:
        return await self._call(
            "blacklist_employer",
            self._tool.api_client.put,
            f"/employers/blacklisted/{employer_id}",
        )

    async def publish_resume(self, resume_id: str) -> dict[str, Any]:
        return await self._call(
            "publish_resume",
            self._tool.api_client.post,
            f"/resumes/{resume_id}/publish",
        )

    async def call_api(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        delay: float | None = None,
    ) -> dict[str, Any]:
        method_upper = method.upper()
        methods = {
            "GET": self._tool.api_client.get,
            "POST": self._tool.api_client.post,
            "PUT": self._tool.api_client.put,
            "DELETE": self._tool.api_client.delete,
        }
        fn = methods.get(method_upper, self._tool.api_client.get)
        return await self._call("call_api", fn, endpoint, params or None, delay=delay)

    async def refresh_token_if_needed(self) -> bool:
        if not self._tool.api_client.is_access_expired:
            return False
        await self._call("refresh_access_token", self._tool.api_client.refresh_access_token)
        await self._call("save_token", self._tool.save_token)
        return True

    async def aclose(self) -> None:
        await self._tool.aclose()
