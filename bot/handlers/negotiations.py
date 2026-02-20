from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.hh_service import HHService
from bot.keyboards import cancel_kb, clear_options
from bot.states import ClearStates, ReplyStates

router = Router()


# ── Negotiations summary ──────────────────────────────────────────────

@router.message(Command("negotiations"))
@router.message(F.text == "📊 Мои отклики")
async def cmd_negotiations(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    wait_msg = await message.answer("⏳ Загрузка откликов...")
    try:
        text = await hh.get_negotiations_summary(message.from_user.id)
        await wait_msg.edit_text(text, parse_mode="HTML")
    except Exception as ex:
        await wait_msg.edit_text(f"❌ Ошибка: {ex}")


# ── Clear negotiations ────────────────────────────────────────────────

@router.message(Command("clear"))
@router.message(F.text == "🗑️ Очистить отклики")
async def cmd_clear(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    await message.answer(
        "🗑️ <b>Очистка откликов</b>\n\n"
        "Выберите, что удалить:",
        reply_markup=clear_options(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "clear_discards")
async def clear_discards(
    callback: CallbackQuery, hh: HHService, state: FSMContext
) -> None:
    await callback.answer()
    msg = await callback.message.edit_text("🗑️ Удаляю отказы...")

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await hh.clear_negotiations(
            callback.from_user.id, callback=progress
        )
    except Exception as ex:
        await msg.edit_text(f"❌ Ошибка: {ex}")


@router.callback_query(F.data == "clear_older")
async def clear_older_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()
    await state.set_state(ClearStates.waiting_for_days)
    await callback.message.edit_text(
        "📅 Введите количество дней.\n"
        "Будут удалены отклики, не обновлявшиеся дольше указанного срока.",
        reply_markup=cancel_kb(),
    )


@router.message(ClearStates.waiting_for_days)
async def clear_older_days(
    message: Message, state: FSMContext, hh: HHService
) -> None:
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число.")
        return

    await state.clear()
    msg = await message.answer(f"🗑️ Удаляю отклики старше {days} дней...")

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await hh.clear_negotiations(
            message.from_user.id, callback=progress, older_than=days
        )
    except Exception as ex:
        await msg.edit_text(f"❌ Ошибка: {ex}")


# ── Reply employers ──────────────────────────────────────────────────

@router.message(Command("reply"))
@router.message(F.text == "💬 Ответить работодателям")
async def cmd_reply(message: Message, hh: HHService, state: FSMContext) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    await state.set_state(ReplyStates.waiting_for_message)
    await message.answer(
        "💬 <b>Ответ работодателям</b>\n\n"
        "Бот отправит сообщение во все чаты, "
        "где есть непрочитанный ответ работодателя.\n\n"
        "Введите шаблон сообщения:\n\n"
        "Плейсхолдеры:\n"
        "<code>%(vacancy_name)s</code> — вакансия\n"
        "<code>%(employer_name)s</code> — работодатель\n"
        "<code>%(first_name)s</code> — ваше имя\n\n"
        "Пример:\n"
        "<code>Здравствуйте! Спасибо за ответ по вакансии "
        "%(vacancy_name)s. Готов обсудить детали.</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ReplyStates.waiting_for_message)
async def reply_message_received(
    message: Message, state: FSMContext, hh: HHService
) -> None:
    reply_text = message.text.strip()
    if not reply_text:
        await message.answer("❌ Сообщение не может быть пустым.")
        return

    await state.clear()
    msg = await message.answer("💬 Рассылаю ответы...")

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await hh.reply_employers(
            message.from_user.id, callback=progress, reply_message=reply_text
        )
    except Exception as ex:
        await msg.edit_text(f"❌ Ошибка: {ex}")


# ── Refresh Token ────────────────────────────────────────────────────

@router.message(Command("refresh"))
@router.message(F.text == "🔄 Обновить токен")
async def cmd_refresh(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    wait_msg = await message.answer("⏳ Проверяю токен...")
    try:
        text = await hh.refresh_token(message.from_user.id)
        await wait_msg.edit_text(text)
    except Exception as ex:
        await wait_msg.edit_text(f"❌ Ошибка обновления токена: {ex}")


# ── Call API ──────────────────────────────────────────────────────────

@router.message(Command("api"))
async def cmd_api(message: Message, hh: HHService) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/api /endpoint [key=value ...]</code>\n\n"
            "Примеры:\n"
            "<code>/api /me</code>\n"
            "<code>/api /employers text=IT</code>",
            parse_mode="HTML",
        )
        return

    endpoint = parts[1]
    params = {}
    if len(parts) > 2:
        for pair in parts[2].split():
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v

    wait_msg = await message.answer("⏳ Запрос к API...")
    try:
        result = await hh.call_api(
            message.from_user.id, "GET", endpoint, **params
        )
        await wait_msg.edit_text(
            f"<pre>{result}</pre>", parse_mode="HTML"
        )
    except Exception as ex:
        await wait_msg.edit_text(f"❌ Ошибка: {ex}")
