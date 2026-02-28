"""
Менеджер аутентификации HH на базе Playwright.

Запускает headless Chromium, заполняет форму входа на HH,
взаимодействует с пользователем Telegram для ввода OTP-кодов и капч.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from bot.services.auth import AuthService
from bot.texts import t

logger = logging.getLogger(__name__)

SendTextFn = Callable[[str], Coroutine[Any, Any, Any]]
SendPhotoFn = Callable[[bytes, str], Coroutine[Any, Any, Any]]
OnSuccessFn = Callable[[str], Coroutine[Any, Any, Any]]

SEL_LOGIN_INPUT = 'input[data-qa="login-input-username"]'
SEL_EXPAND_PASSWORD = 'button[data-qa="expand-login-by_password"]'
SEL_PASSWORD_INPUT = 'input[data-qa="login-input-password"]'
SEL_CODE_CONTAINER = 'div[data-qa="account-login-code-input"]'
SEL_PIN_CODE_INPUT = 'input[data-qa="magritte-pincode-input-field"]'
SEL_CAPTCHA_IMAGE = 'img[data-qa="account-captcha-picture"]'
SEL_CAPTCHA_INPUT = 'input[data-qa="account-captcha-input"]'

HH_ANDROID_SCHEME = "hhandroid"
INPUT_TIMEOUT = 300  # 5 minutes


@dataclass
class _AuthSession:
    input_event: asyncio.Event = field(default_factory=asyncio.Event)
    input_value: str = ""
    cancelled: bool = False


class AuthManager:
    """Управление интерактивными Playwright-сессиями входа для каждого пользователя."""

    def __init__(self, auth_service: AuthService) -> None:
        self.auth = auth_service
        self._sessions: dict[int, _AuthSession] = {}

    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, запущена ли сессия входа для указанного пользователя."""
        return user_id in self._sessions

    async def provide_input(self, user_id: int, text: str) -> bool:
        """Передаёт введённый пользователем текст (OTP / капча) в текущую сессию."""
        session = self._sessions.get(user_id)
        if session:
            session.input_value = text
            session.input_event.set()
            return True
        return False

    async def cancel(self, user_id: int) -> None:
        """Отменяет активную сессию входа."""
        session = self._sessions.pop(user_id, None)
        if session:
            session.cancelled = True
            session.input_event.set()

    async def start_login(
        self,
        user_id: int,
        username: str,
        password: str | None,
        send_text: SendTextFn,
        send_photo: SendPhotoFn,
        on_success: OnSuccessFn | None = None,
    ) -> None:
        """Запускает новую Playwright-сессию входа в фоновом режиме."""
        if user_id in self._sessions:
            await send_text(t("auth.already_in_progress"))
            return
        session = _AuthSession()
        self._sessions[user_id] = session
        asyncio.create_task(
            self._run_auth(user_id, session, username, password, send_text, send_photo, on_success)
        )

    async def _wait_for_input(self, session: _AuthSession) -> str | None:
        session.input_event.clear()
        session.input_value = ""
        try:
            await asyncio.wait_for(session.input_event.wait(), timeout=INPUT_TIMEOUT)
        except asyncio.TimeoutError:
            return None
        if session.cancelled:
            return None
        return session.input_value

    async def _handle_captcha(
        self,
        page: Any,
        session: _AuthSession,
        send_text: SendTextFn,
        send_photo: SendPhotoFn,
    ) -> None:
        try:
            captcha_el = await page.wait_for_selector(
                SEL_CAPTCHA_IMAGE, timeout=5000, state="visible"
            )
        except Exception:
            return

        img_bytes = await captcha_el.screenshot()
        await send_photo(img_bytes, t("auth.captcha_prompt"))

        captcha_text = await self._wait_for_input(session)
        if not captcha_text:
            raise RuntimeError(t("auth.captcha_timeout"))

        await page.fill(SEL_CAPTCHA_INPUT, captcha_text)
        await page.press(SEL_CAPTCHA_INPUT, "Enter")
        await asyncio.sleep(1)

    async def _run_auth(
        self,
        user_id: int,
        session: _AuthSession,
        username: str,
        password: str | None,
        send_text: SendTextFn,
        send_photo: SendPhotoFn,
        on_success: OnSuccessFn | None = None,
    ) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            await send_text(t("auth.playwright_missing"))
            self._sessions.pop(user_id, None)
            return

        try:
            tool = self.auth._get_tool(user_id)
            oauth_client = tool.api_client.oauth_client

            proxies = tool.api_client.proxies or {}
            proxy_url = proxies.get("https")
            chromium_args: list[str] = []
            if proxy_url:
                chromium_args.append(f"--proxy-server={proxy_url}")

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True, args=chromium_args
                )
                try:
                    android_device = pw.devices["Galaxy A55"]
                    context = await browser.new_context(**android_device)
                    page = await context.new_page()

                    code_future: asyncio.Future[str | None] = asyncio.Future()

                    def on_request(request: Any) -> None:
                        url = request.url
                        if url.startswith(f"{HH_ANDROID_SCHEME}://"):
                            if not code_future.done():
                                sp = urlsplit(url)
                                code = parse_qs(sp.query).get("code", [None])[0]
                                code_future.set_result(code)

                    page.on("request", on_request)

                    await send_text(t("auth.opening_page"))
                    await page.goto(
                        oauth_client.authorize_url,
                        timeout=30000,
                        wait_until="load",
                    )

                    await page.wait_for_selector(SEL_LOGIN_INPUT, timeout=15000)
                    await page.fill(SEL_LOGIN_INPUT, username)

                    if password:
                        await send_text(t("auth.entering_password"))
                        await page.click(SEL_EXPAND_PASSWORD)
                        await self._handle_captcha(page, session, send_text, send_photo)
                        await page.wait_for_selector(SEL_PASSWORD_INPUT, timeout=10000)
                        await page.fill(SEL_PASSWORD_INPUT, password)
                        await page.press(SEL_PASSWORD_INPUT, "Enter")
                    else:
                        await page.press(SEL_LOGIN_INPUT, "Enter")
                        await self._handle_captcha(page, session, send_text, send_photo)

                        try:
                            await page.wait_for_selector(
                                SEL_CODE_CONTAINER, timeout=15000
                            )
                        except Exception:
                            await send_text(t("auth.code_form_timeout"))
                            return

                        await send_text(t("auth.code_sent"))

                        code = await self._wait_for_input(session)
                        if not code:
                            await send_text(t("auth.code_timeout"))
                            return

                        await page.fill(SEL_PIN_CODE_INPUT, code)
                        await page.press(SEL_PIN_CODE_INPUT, "Enter")

                    await send_text(t("auth.waiting_confirmation"))

                    auth_code = await asyncio.wait_for(code_future, timeout=30)
                    if not auth_code:
                        await send_text(t("auth.no_auth_code"))
                        return

                    page.remove_listener("request", on_request)

                    token = await asyncio.to_thread(
                        oauth_client.authenticate, auth_code
                    )
                    tool.api_client.handle_access_token(token)

                    self.auth.save_tokens(
                        user_id,
                        token["access_token"],
                        token["refresh_token"],
                        token["access_expires_at"],
                    )

                    await self._save_cookies(context, tool.cookies_file)

                    try:
                        info = await self.auth.whoami(user_id)
                        msg = t("auth.success_with_info", info=info)
                    except Exception:
                        msg = t("auth.success")

                    if on_success:
                        await on_success(msg)
                    else:
                        await send_text(msg)

                finally:
                    await browser.close()

        except asyncio.TimeoutError:
            await send_text(t("auth.timeout"))
        except Exception as ex:
            logger.exception("Auth error for user %d", user_id)
            await send_text(t("auth.error", error=ex))
        finally:
            self._sessions.pop(user_id, None)

    @staticmethod
    async def _save_cookies(context: Any, cookies_file: Path) -> None:
        """Экспортирует cookie браузера в файл формата Netscape."""
        cookies = await context.cookies()
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Generated by hh-bot\n\n")
            for c in cookies:
                domain = c["domain"]
                if c.get("httpOnly"):
                    domain = f"#HttpOnly_{domain}"
                flag = "TRUE" if c["domain"].startswith(".") else "FALSE"
                path = c["path"]
                secure = "TRUE" if c["secure"] else "FALSE"
                expires = int(c.get("expires") or 0)
                name = c["name"]
                value = c["value"]
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
