"""Primary async gateway для HH API."""

from __future__ import annotations

from typing import Any

from hh_applicant_tool import HHApplicantTool

from bot.services.hh_gateway import GatewayInstrumentationMixin


class AsyncHHGateway(GatewayInstrumentationMixin):
    """Primary async-адаптер над HHApplicantTool.

    Используется как основной transport для сервисов; sync-клиент в tool
    поддерживается в консистентном состоянии токенов для fallback-путей.
    """

    def __init__(self, user_id: int, tool: HHApplicantTool) -> None:
        super().__init__(user_id=user_id)
        self._tool = tool

    def get_oauth_url(self) -> str:
        return self._tool.api_client.oauth_client.authorize_url

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Обменивает OAuth code на токен и синхронизирует оба клиента."""
        async def _wrapped() -> dict[str, Any]:
            token = await self._tool.async_api_client.oauth_client.authenticate(code)
            # Токен записываем в sync и async клиенты, чтобы любой путь gateway
            # видел одинаковое auth-состояние без дополнительного refresh.
            self._tool.api_client.handle_access_token(token)
            self._tool.async_api_client.handle_access_token(token)
            await self._tool.asave_token()
            return token

        return await self._observe("oauth.authenticate", _wrapped)

    async def get_me(self) -> dict[str, Any]:
        return await self._observe("get_me", self._tool.aget_me)

    async def get_resumes(self) -> list[dict[str, Any]]:
        return await self._observe("get_resumes", self._tool.aget_resumes)

    async def get_negotiations(self, status: str = "active") -> list[dict[str, Any]]:
        return await self._observe(
            "get_negotiations",
            lambda: self._tool.aget_negotiations(status=status),
        )

    async def get_blacklisted(self) -> list[str]:
        return await self._observe("get_blacklisted", self._tool.aget_blacklisted)

    async def get_negotiation_messages(self, negotiation_id: str) -> dict[str, Any]:
        return await self._observe(
            "get_negotiation_messages",
            lambda: self._tool.async_api_client.get(
                f"/negotiations/{negotiation_id}/messages"
            ),
        )

    async def create_negotiation(
        self,
        resume_id: str,
        vacancy_id: str,
        message: str,
        delay: float | None = None,
    ) -> dict[str, Any]:
        return await self._observe(
            "create_negotiation",
            lambda: self._tool.async_api_client.post(
                "/negotiations",
                {
                    "resume_id": resume_id,
                    "vacancy_id": vacancy_id,
                    "message": message,
                },
                delay=delay,
            ),
        )

    async def delete_negotiation(self, negotiation_id: str) -> dict[str, Any]:
        return await self._observe(
            "delete_negotiation",
            lambda: self._tool.async_api_client.delete(
                f"/negotiations/active/{negotiation_id}",
                {"with_decline_message": True},
            ),
        )

    async def blacklist_employer(self, employer_id: str) -> dict[str, Any]:
        return await self._observe(
            "blacklist_employer",
            lambda: self._tool.async_api_client.put(f"/employers/blacklisted/{employer_id}"),
        )

    async def publish_resume(self, resume_id: str) -> dict[str, Any]:
        return await self._observe(
            "publish_resume",
            lambda: self._tool.async_api_client.post(f"/resumes/{resume_id}/publish"),
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
            "GET": self._tool.async_api_client.get,
            "POST": self._tool.async_api_client.post,
            "PUT": self._tool.async_api_client.put,
            "DELETE": self._tool.async_api_client.delete,
        }
        fn = methods.get(method_upper, self._tool.async_api_client.get)
        return await self._observe(
            "call_api",
            lambda: fn(endpoint, params or None, delay=delay),
        )

    async def refresh_token_if_needed(self) -> bool:
        """Обновляет токен только при истечении и сохраняет его в конфиг."""
        if not self._tool.async_api_client.is_access_expired:
            return False

        async def _wrapped() -> bool:
            await self._tool.arefresh_access_token()
            await self._tool.asave_token()
            return True

        return await self._observe("refresh_access_token", _wrapped)

    async def aclose(self) -> None:
        await self._tool.aclose()
