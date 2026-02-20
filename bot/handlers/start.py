from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.hh_service import HHService
from bot.keyboards import auth_menu, main_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, hh: HHService, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id

    if not config.is_user_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    if hh.is_authenticated(user_id):
        await message.answer(
            "👋 С возвращением! Выберите действие:",
            reply_markup=main_menu(),
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в <b>HH Bot</b>!\n\n"
            "Этот бот поможет автоматизировать поиск работы на hh.ru:\n"
            "• Массовая рассылка откликов\n"
            "• Обновление резюме\n"
            "• Ответы работодателям\n"
            "• Управление откликами\n\n"
            "Для начала необходимо авторизоваться.",
            reply_markup=auth_menu(),
            parse_mode="HTML",
        )


@router.message(Command("help"))
@router.message(F.text == "⚙️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>📖 Справка по командам</b>\n\n"
        "<b>Основные:</b>\n"
        "/start — Главное меню\n"
        "/whoami — Информация о профиле\n"
        "/resumes — Список резюме\n"
        "/update — Обновить все резюме\n\n"
        "<b>Отклики:</b>\n"
        "/apply — Рассылка откликов\n"
        "/negotiations — Статистика откликов\n"
        "/clear — Очистка откликов\n"
        "/reply — Ответ работодателям\n\n"
        "<b>Прочее:</b>\n"
        "/refresh — Обновить токен доступа\n"
        "/logout — Выйти из аккаунта\n"
        "/api — Вызов метода HH API\n\n"
        "<b>Шаблоны сообщений</b>\n"
        "Плейсхолдеры: <code>%(vacancy_name)s</code>, "
        "<code>%(employer_name)s</code>, <code>%(first_name)s</code>, "
        "<code>%(last_name)s</code>, <code>%(resume_title)s</code>\n"
        "Варианты: <code>{Привет|Здравствуйте}</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()
