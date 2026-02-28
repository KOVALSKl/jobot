"""Обработчики /start, /help и глобальной отмены."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import auth_menu, main_menu
from bot.services.auth import AuthService
from bot.texts import t

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, auth_service: AuthService, state: FSMContext) -> None:
    """Отображает главное меню или экран приветствия в зависимости от статуса авторизации."""
    await state.clear()
    user_id = message.from_user.id

    if auth_service.is_authenticated(user_id):
        await message.answer(t("start.welcome_back"), reply_markup=main_menu())
    else:
        await message.answer(
            t("start.welcome"), reply_markup=auth_menu(), parse_mode="HTML",
        )


@router.message(Command("help"))
@router.message(F.text == "⚙️ Помощь")
async def cmd_help(message: Message) -> None:
    """Отображает список всех доступных команд."""
    await message.answer(t("start.help"), parse_mode="HTML")


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет текущую FSM-операцию."""
    await state.clear()
    await callback.message.edit_text(t("start.cancelled"))
    await callback.answer()
