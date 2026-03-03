"""Обработчики аутентификации HH: вход, выход, профиль, управление токенами."""

from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.auth_manager import AuthManager
from bot.decorators import require_auth
from bot.keyboards import cancel_kb, logout_confirm, main_menu, password_choice
from bot.services.auth import AuthService
from bot.services.tasks import ACTIVE_TASK_STATUSES, TaskQueueService
from bot.states import AuthStates
from bot.texts import t

router = Router()


# ── Main login flow (Playwright) ─────────────────────────────────────

@router.message(F.text == "🔑 Войти в HH")
@router.message(Command("login"))
async def login_start(message: Message, state: FSMContext) -> None:
    """Запускает процесс входа в HH через Playwright."""
    queue = TaskQueueService()
    task = await queue.get_user_task(user_id=message.from_user.id)
    if task is not None and task.status in ACTIVE_TASK_STATUSES:
        await message.answer(
            "⚠️ Пока выполняется тяжёлая задача, авторизацию запускать нельзя.\n"
            "Дождитесь завершения и попробуйте снова."
        )
        return
    await state.set_state(AuthStates.waiting_for_username)
    await message.answer(
        t("auth.login_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AuthStates.waiting_for_username)
async def login_username_received(message: Message, state: FSMContext) -> None:
    """Валидирует имя пользователя и предлагает выбор способа входа."""
    username = message.text.strip()
    if not username or len(username) < 3:
        await message.answer(t("auth.invalid_username"))
        return

    await state.update_data(username=username)
    await state.set_state(AuthStates.waiting_for_password_choice)
    await message.answer(
        t("auth.login_confirm", username=username),
        parse_mode="HTML",
        reply_markup=password_choice(),
    )


@router.callback_query(F.data == "auth_otp")
async def login_otp(
    callback: CallbackQuery, state: FSMContext, auth_manager: AuthManager
) -> None:
    """Инициирует вход через OTP с использованием Playwright."""
    await callback.answer()
    data = await state.get_data()
    username = data.get("username", "")

    await state.set_state(AuthStates.auth_in_progress)
    await callback.message.edit_text(t("auth.starting"))

    async def send_text(text: str) -> None:
        try:
            await callback.message.answer(text, parse_mode="HTML")
        except Exception:
            pass

    async def send_photo(img_bytes: bytes, caption: str) -> None:
        try:
            photo = BufferedInputFile(img_bytes, filename="captcha.png")
            await callback.message.answer_photo(photo, caption=caption)
        except Exception:
            pass

    async def on_success(text: str) -> None:
        try:
            await state.clear()
            await callback.message.answer(
                text, parse_mode="HTML", reply_markup=main_menu()
            )
        except Exception:
            pass

    await auth_manager.start_login(
        user_id=callback.from_user.id,
        username=username,
        password=None,
        send_text=send_text,
        send_photo=send_photo,
        on_success=on_success,
    )


@router.callback_query(F.data == "auth_password")
async def login_password_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Запрашивает пароль для входа в HH."""
    await callback.answer()
    await state.set_state(AuthStates.waiting_for_password)
    await callback.message.edit_text(t("auth.password_prompt"), parse_mode="HTML")


@router.message(AuthStates.waiting_for_password)
async def login_password_received(
    message: Message, state: FSMContext, auth_manager: AuthManager
) -> None:
    """Обрабатывает пароль и запускает Playwright-сессию входа."""
    password = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not password:
        await message.answer(t("auth.empty_password"))
        return

    data = await state.get_data()
    username = data.get("username", "")

    await state.set_state(AuthStates.auth_in_progress)

    async def send_text(text: str) -> None:
        try:
            await message.answer(text, parse_mode="HTML")
        except Exception:
            pass

    async def send_photo(img_bytes: bytes, caption: str) -> None:
        try:
            photo = BufferedInputFile(img_bytes, filename="captcha.png")
            await message.answer_photo(photo, caption=caption)
        except Exception:
            pass

    async def on_success(text: str) -> None:
        try:
            await state.clear()
            await message.answer(
                text, parse_mode="HTML", reply_markup=main_menu()
            )
        except Exception:
            pass

    await auth_manager.start_login(
        user_id=message.from_user.id,
        username=username,
        password=password,
        send_text=send_text,
        send_photo=send_photo,
        on_success=on_success,
    )


@router.message(AuthStates.auth_in_progress)
async def auth_input_handler(
    message: Message, state: FSMContext, auth_manager: AuthManager, auth_service: AuthService
) -> None:
    """Передаёт ввод пользователя (OTP-код / капча) в активную сессию авторизации."""
    text = message.text.strip() if message.text else ""

    if text.lower() in ("/cancel", "отмена"):
        await auth_manager.cancel(message.from_user.id)
        await state.clear()
        await message.answer(t("auth.cancelled"))
        return

    provided = await auth_manager.provide_input(message.from_user.id, text)
    if not provided:
        await state.clear()
        if await auth_service.is_authenticated(message.from_user.id):
            await message.answer(
                t("auth.already_authenticated"),
                reply_markup=main_menu(),
            )
        else:
            await message.answer(t("auth.session_ended"))


# ── Fallback: login via tokens ───────────────────────────────────────

@router.message(F.text == "🔐 Войти через токены")
@router.message(Command("login_tokens"))
async def login_tokens_start(message: Message, state: FSMContext) -> None:
    """Запрашивает ручной ввод access/refresh токенов."""
    await state.set_state(AuthStates.waiting_for_tokens)
    await message.answer(
        t("auth.tokens_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AuthStates.waiting_for_tokens)
async def login_tokens_receive(
    message: Message, state: FSMContext, auth_service: AuthService
) -> None:
    lines = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        await message.answer(t("auth.tokens_invalid_format"))
        return

    access_token = lines[0]
    refresh_token = lines[1]

    if not access_token.startswith("USER"):
        await message.answer(t("auth.tokens_invalid_prefix"))
        return

    expires_at = int(time.time()) + 14 * 24 * 3600
    await auth_service.save_tokens(
        message.from_user.id,
        access_token,
        refresh_token,
        expires_at,
    )

    try:
        info = await auth_service.whoami(message.from_user.id)
        await state.clear()
        await message.answer(
            t("auth.tokens_success", info=info),
            reply_markup=main_menu(),
            parse_mode="HTML",
        )
    except Exception as ex:
        await auth_service.logout(message.from_user.id)
        await message.answer(t("auth.tokens_failed", error=ex))


# ── Whoami ───────────────────────────────────────────────────────────

@router.message(Command("whoami"))
@router.message(F.text == "👤 Профиль")
@require_auth
async def cmd_whoami(message: Message, auth_service: AuthService) -> None:
    """Отображает информацию о текущем профиле HH."""
    wait_msg = await message.answer(t("auth.loading_profile"))
    try:
        info = await auth_service.whoami(message.from_user.id)
        await wait_msg.edit_text(info, parse_mode="HTML")
    except Exception as ex:
        await wait_msg.edit_text(t("common.error", error=ex))


# ── Logout ───────────────────────────────────────────────────────────

@router.message(Command("logout"))
@require_auth
async def cmd_logout(message: Message, auth_service: AuthService) -> None:
    """Запрашивает подтверждение выхода из аккаунта."""
    await message.answer(t("auth.logout_confirm"), reply_markup=logout_confirm())


@router.callback_query(F.data == "logout_yes")
async def logout_confirm_cb(
    callback: CallbackQuery, auth_service: AuthService, state: FSMContext
) -> None:
    """Выполняет выход из аккаунта после подтверждения."""
    await auth_service.logout(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(t("auth.logged_out"))
    await callback.answer()
