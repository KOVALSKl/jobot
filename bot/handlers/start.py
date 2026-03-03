"""Обработчики /start, /help и глобальной отмены."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.decorators import require_auth
from bot.keyboards import auth_menu, main_menu
from bot.services.auth import AuthService
from bot.services.heavy_queue import cancel_user_task, render_task_status
from bot.services.tasks import TaskQueueService
from bot.texts import t

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, auth_service: AuthService, state: FSMContext) -> None:
    """Отображает главное меню или экран приветствия в зависимости от статуса авторизации."""
    await state.clear()
    user_id = message.from_user.id

    if await auth_service.is_authenticated(user_id):
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


@router.message(Command("status"))
@router.message(F.text == "📌 Статус задачи")
@require_auth
async def cmd_status(message: Message, auth_service: AuthService) -> None:
    """Показывает статус последней фоновой задачи пользователя."""
    queue = TaskQueueService()
    task = await queue.get_user_task(user_id=message.from_user.id)
    await message.answer(render_task_status(task), parse_mode="HTML")


@router.message(Command("cancel_task"))
@require_auth
async def cmd_cancel_task(message: Message, auth_service: AuthService) -> None:
    """Запрашивает отмену активной фоновой задачи пользователя."""
    task = await cancel_user_task(user_id=message.from_user.id)
    if task is None:
        await message.answer("ℹ️ У вас нет активных задач для отмены.")
        return
    await message.answer(
        "🛑 Запрос на отмену отправлен.\n"
        f"ID: <code>{task.task_id}</code>\n"
        "Проверьте статус через /status",
        parse_mode="HTML",
    )
