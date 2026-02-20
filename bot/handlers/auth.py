from __future__ import annotations

import time
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.auth_manager import AuthManager
from bot.hh_service import HHService
from bot.keyboards import cancel_kb, logout_confirm, main_menu, password_choice
from bot.states import AuthStates

router = Router()


# ── Main login flow (Playwright) ─────────────────────────────────────

@router.message(F.text == "🔑 Войти в HH")
@router.message(Command("login"))
async def login_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthStates.waiting_for_username)
    await message.answer(
        "👤 <b>Вход в аккаунт HH</b>\n\n"
        "Введите ваш email или номер телефона:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AuthStates.waiting_for_username)
async def login_username_received(message: Message, state: FSMContext) -> None:
    username = message.text.strip()
    if not username or len(username) < 3:
        await message.answer("❌ Введите корректный email или телефон.")
        return

    await state.update_data(username=username)
    await state.set_state(AuthStates.waiting_for_password_choice)
    await message.answer(
        f"📧 Логин: <code>{username}</code>\n\n"
        "Выберите способ входа:",
        parse_mode="HTML",
        reply_markup=password_choice(),
    )


@router.callback_query(F.data == "auth_otp")
async def login_otp(
    callback: CallbackQuery, state: FSMContext, auth: AuthManager
) -> None:
    await callback.answer()
    data = await state.get_data()
    username = data.get("username", "")

    await state.set_state(AuthStates.auth_in_progress)
    await callback.message.edit_text("⏳ Начинаю авторизацию...")

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

    await auth.start_login(
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
    await callback.answer()
    await state.set_state(AuthStates.waiting_for_password)
    await callback.message.edit_text(
        "🔒 Введите пароль от аккаунта HH:\n\n"
        "<i>Сообщение с паролем будет удалено после обработки.</i>",
        parse_mode="HTML",
    )


@router.message(AuthStates.waiting_for_password)
async def login_password_received(
    message: Message, state: FSMContext, auth: AuthManager
) -> None:
    password = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not password:
        await message.answer("❌ Пароль не может быть пустым.")
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

    await auth.start_login(
        user_id=message.from_user.id,
        username=username,
        password=password,
        send_text=send_text,
        send_photo=send_photo,
        on_success=on_success,
    )


@router.message(AuthStates.auth_in_progress)
async def auth_input_handler(
    message: Message, state: FSMContext, auth: AuthManager, hh: HHService
) -> None:
    """Перехватывает ввод пользователя (код/капча) во время авторизации."""
    text = message.text.strip() if message.text else ""

    if text.lower() in ("/cancel", "отмена"):
        await auth.cancel(message.from_user.id)
        await state.clear()
        await message.answer("❌ Авторизация отменена.")
        return

    provided = await auth.provide_input(message.from_user.id, text)
    if not provided:
        await state.clear()
        if hh.is_authenticated(message.from_user.id):
            await message.answer(
                "✅ Вы авторизованы! Выберите действие:",
                reply_markup=main_menu(),
            )
        else:
            await message.answer("Сессия авторизации завершена. Попробуйте /login")


# ── Fallback: login via tokens ───────────────────────────────────────

@router.message(F.text == "🔐 Войти через токены")
@router.message(Command("login_tokens"))
async def login_tokens_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthStates.waiting_for_tokens)
    await message.answer(
        "🔐 <b>Авторизация через токены</b>\n\n"
        "Отправьте токены в формате (каждый на новой строке):\n"
        "<code>access_token</code>\n"
        "<code>refresh_token</code>\n\n"
        "<b>Как получить:</b>\n"
        "1. <code>hh-applicant-tool auth</code>\n"
        "2. <code>hh-applicant-tool config</code>\n"
        "3. Скопируйте access_token и refresh_token",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AuthStates.waiting_for_tokens)
async def login_tokens_receive(
    message: Message, state: FSMContext, hh: HHService
) -> None:
    lines = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        await message.answer(
            "❌ Нужно 2 строки: access_token и refresh_token.\nПопробуйте ещё раз."
        )
        return

    access_token = lines[0]
    refresh_token = lines[1]

    if not access_token.startswith("USER"):
        await message.answer("❌ access_token должен начинаться с 'USER'.")
        return

    expires_at = int(time.time()) + 14 * 24 * 3600
    hh.save_tokens(message.from_user.id, access_token, refresh_token, expires_at)

    try:
        info = await hh.whoami(message.from_user.id)
        await state.clear()
        await message.answer(
            f"✅ Авторизация успешна!\n\n{info}",
            reply_markup=main_menu(),
            parse_mode="HTML",
        )
    except Exception as ex:
        hh.logout(message.from_user.id)
        await message.answer(f"❌ Не удалось авторизоваться: {ex}")


# ── Whoami ───────────────────────────────────────────────────────────

@router.message(Command("whoami"))
@router.message(F.text == "👤 Профиль")
async def cmd_whoami(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    wait_msg = await message.answer("⏳ Загрузка профиля...")
    try:
        info = await hh.whoami(message.from_user.id)
        await wait_msg.edit_text(info, parse_mode="HTML")
    except Exception as ex:
        await wait_msg.edit_text(f"❌ Ошибка: {ex}")


# ── Logout ───────────────────────────────────────────────────────────

@router.message(Command("logout"))
async def cmd_logout(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("Вы и так не авторизованы.")
        return
    await message.answer(
        "Вы уверены, что хотите выйти?", reply_markup=logout_confirm()
    )


@router.callback_query(F.data == "logout_yes")
async def logout_confirm_cb(
    callback: CallbackQuery, hh: HHService, state: FSMContext
) -> None:
    hh.logout(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text("✅ Вы вышли из аккаунта.")
    await callback.answer()
