"""Обработчики откликов: просмотр, очистка, ответы работодателям, обновление токена и прямые API-вызовы."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.decorators import require_auth
from bot.keyboards import cancel_kb, clear_options
from bot.services.api import ApiService
from bot.services.auth import AuthService
from bot.services.negotiation import NegotiationService
from bot.states import ClearStates, ReplyStates
from bot.texts import t

router = Router()


# ── Negotiations summary ──────────────────────────────────────────────

@router.message(Command("negotiations"))
@router.message(F.text == "📊 Мои отклики")
@require_auth
async def cmd_negotiations(message: Message, auth_service: AuthService, negotiation_service: NegotiationService) -> None:
    """Отображает агрегированную статистику откликов."""
    wait_msg = await message.answer(t("negotiations.loading"))
    try:
        text = await negotiation_service.get_summary(message.from_user.id)
        await wait_msg.edit_text(text, parse_mode="HTML")
    except Exception as ex:
        await wait_msg.edit_text(t("common.error", error=ex))


# ── Clear negotiations ────────────────────────────────────────────────

@router.message(Command("clear"))
@router.message(F.text == "🗑️ Очистить отклики")
@require_auth
async def cmd_clear(message: Message, auth_service: AuthService) -> None:
    """Отображает меню параметров очистки откликов."""
    await message.answer(
        t("negotiations.clear_prompt"),
        reply_markup=clear_options(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "clear_discards")
async def clear_discards(
    callback: CallbackQuery, negotiation_service: NegotiationService, state: FSMContext
) -> None:
    """Удаляет все отклики со статусом 'отклонено'."""
    await callback.answer()
    msg = await callback.message.edit_text(t("negotiations.clearing_discards"))

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await negotiation_service.clear(
            callback.from_user.id, callback=progress
        )
    except Exception as ex:
        await msg.edit_text(t("common.error", error=ex))


@router.callback_query(F.data == "clear_older")
async def clear_older_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Запрашивает количество дней неактивности для очистки."""
    await callback.answer()
    await state.set_state(ClearStates.waiting_for_days)
    await callback.message.edit_text(
        t("negotiations.days_prompt"),
        reply_markup=cancel_kb(),
    )


@router.message(ClearStates.waiting_for_days)
async def clear_older_days(
    message: Message, state: FSMContext, negotiation_service: NegotiationService
) -> None:
    """Парсит количество дней и очищает старые отклики."""
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(t("common.invalid_number"))
        return

    await state.clear()
    msg = await message.answer(t("negotiations.clearing_older", days=days))

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await negotiation_service.clear(
            message.from_user.id, callback=progress, older_than=days
        )
    except Exception as ex:
        await msg.edit_text(t("common.error", error=ex))


# ── Reply employers ──────────────────────────────────────────────────

@router.message(Command("reply"))
@router.message(F.text == "💬 Ответить работодателям")
@require_auth
async def cmd_reply(message: Message, auth_service: AuthService, state: FSMContext) -> None:
    """Запрашивает шаблон сообщения для ответа работодателям."""
    await state.set_state(ReplyStates.waiting_for_message)
    await message.answer(
        t("negotiations.reply_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ReplyStates.waiting_for_message)
async def reply_message_received(
    message: Message, state: FSMContext, negotiation_service: NegotiationService
) -> None:
    """Отправляет ответы на все непрочитанные сообщения работодателей."""
    reply_text = message.text.strip()
    if not reply_text:
        await message.answer(t("common.empty_message"))
        return

    await state.clear()
    msg = await message.answer(t("negotiations.replying"))

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await negotiation_service.reply_employers(
            message.from_user.id, callback=progress, reply_message=reply_text
        )
    except Exception as ex:
        await msg.edit_text(t("common.error", error=ex))


# ── Refresh Token ────────────────────────────────────────────────────

@router.message(Command("refresh"))
@router.message(F.text == "🔄 Обновить токен")
@require_auth
async def cmd_refresh(message: Message, auth_service: AuthService) -> None:
    """Обновляет access-токен HH API, если он истёк."""
    wait_msg = await message.answer(t("token.checking"))
    try:
        text = await auth_service.refresh_token(message.from_user.id)
        await wait_msg.edit_text(text)
    except Exception as ex:
        await wait_msg.edit_text(t("token.refresh_error", error=ex))


# ── Call API ──────────────────────────────────────────────────────────

@router.message(Command("api"))
@require_auth
async def cmd_api(message: Message, auth_service: AuthService, api_service: ApiService) -> None:
    """Выполняет прямой вызов к HH API (GET по умолчанию)."""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(t("api.usage"), parse_mode="HTML")
        return

    endpoint = parts[1]
    params = {}
    if len(parts) > 2:
        for pair in parts[2].split():
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v

    wait_msg = await message.answer(t("api.loading"))
    try:
        result = await api_service.call_api(
            message.from_user.id, "GET", endpoint, **params
        )
        await wait_msg.edit_text(
            f"<pre>{result}</pre>", parse_mode="HTML"
        )
    except Exception as ex:
        await wait_msg.edit_text(t("common.error", error=ex))
