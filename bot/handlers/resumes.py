from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.hh_service import HHService
from bot.keyboards import resume_actions

router = Router()


@router.message(Command("resumes"))
@router.message(F.text == "📄 Мои резюме")
async def cmd_resumes(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    wait_msg = await message.answer("⏳ Загрузка резюме...")
    try:
        text = await hh.list_resumes(message.from_user.id)
        await wait_msg.edit_text(
            text, reply_markup=resume_actions(), parse_mode="HTML"
        )
    except Exception as ex:
        await wait_msg.edit_text(f"❌ Ошибка: {ex}")


@router.message(Command("update"))
@router.callback_query(F.data == "update_resumes")
async def cmd_update_resumes(
    event: Message | CallbackQuery, hh: HHService
) -> None:
    user_id = event.from_user.id
    if not hh.is_authenticated(user_id):
        text = "⚠️ Вы не авторизованы. Используйте /start"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = await event.message.edit_text("⏳ Обновляю резюме...")
    else:
        msg = await event.answer("⏳ Обновляю резюме...")

    try:
        result = await hh.update_resumes(user_id)
        await msg.edit_text(result, parse_mode="HTML")
    except Exception as ex:
        await msg.edit_text(f"❌ Ошибка: {ex}")
