from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.hh_service import HHService
from bot.keyboards import apply_confirm, apply_options, cancel_kb
from bot.states import ApplyStates

router = Router()


@router.message(Command("apply"))
@router.message(F.text == "🚀 Рассылка откликов")
async def cmd_apply(message: Message, hh: HHService, state: FSMContext) -> None:
    if not hh.is_authenticated(message.from_user.id):
        await message.answer("⚠️ Вы не авторизованы. Используйте /start")
        return

    await state.clear()
    await message.answer(
        "🚀 <b>Рассылка откликов</b>\n\n"
        "Утилита откликнется на все подходящие вакансии "
        "со всех опубликованных резюме.\n\n"
        "Выберите режим:",
        reply_markup=apply_options(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "apply_default")
async def apply_default(
    callback: CallbackQuery, hh: HHService, state: FSMContext
) -> None:
    await callback.answer()
    await _run_apply(callback.message, callback.from_user.id, hh, state)


@router.callback_query(F.data == "apply_search")
async def apply_search_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()
    await state.set_state(ApplyStates.waiting_for_search)
    await callback.message.edit_text(
        "🔍 Введите поисковый запрос для вакансий.\n\n"
        "Примеры:\n"
        "• <code>Python backend</code>\n"
        "• <code>(Go OR Golang) NOT PHP</code>\n"
        "• <code>DevOps инженер</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить.",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_search)
async def apply_search_received(message: Message, state: FSMContext) -> None:
    search = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(search=search)
    await state.set_state(ApplyStates.waiting_for_excluded)
    await message.answer(
        "🚫 Укажите исключаемые слова через запятую.\n\n"
        "Вакансии, содержащие эти слова в названии или описании, "
        "будут пропущены.\n\n"
        "Пример: <code>fullstack, junior, php, bitrix</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить.",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_excluded)
async def apply_excluded_received(message: Message, state: FSMContext) -> None:
    excluded = (
        message.text.strip() if message.text.strip() != "-" else None
    )
    await state.update_data(excluded=excluded)
    await state.set_state(ApplyStates.waiting_for_message)
    await message.answer(
        "✉️ Введите шаблон сопроводительного письма (необязательно).\n\n"
        "Доступные плейсхолдеры:\n"
        "<code>%(vacancy_name)s</code> — название вакансии\n"
        "<code>%(employer_name)s</code> — работодатель\n"
        "<code>%(first_name)s</code> — ваше имя\n"
        "<code>%(last_name)s</code> — фамилия\n"
        "<code>%(resume_title)s</code> — название резюме\n\n"
        "Рандомизация: <code>{Привет|Здравствуйте}</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить.",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_message)
async def apply_message_received(
    message: Message, state: FSMContext, hh: HHService
) -> None:
    msg_template = (
        message.text.strip() if message.text.strip() != "-" else None
    )
    await state.update_data(message_template=msg_template)

    data = await state.get_data()
    search = data.get("search")
    excluded = data.get("excluded")

    summary_parts = ["<b>Параметры рассылки:</b>"]
    summary_parts.append(f"🔍 Поиск: {search or 'все подходящие'}")
    summary_parts.append(f"🚫 Исключения: {excluded or 'нет'}")
    summary_parts.append(
        f"✉️ Письмо: {'задано' if msg_template else 'без письма'}"
    )

    await state.set_state(ApplyStates.confirm)
    await message.answer(
        "\n".join(summary_parts),
        reply_markup=apply_confirm(search, excluded),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "apply_go")
async def apply_go(
    callback: CallbackQuery, hh: HHService, state: FSMContext
) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    await _run_apply(
        callback.message,
        callback.from_user.id,
        hh,
        state,
        search=data.get("search"),
        excluded=data.get("excluded"),
        message_template=data.get("message_template"),
    )


async def _run_apply(
    message: Message,
    user_id: int,
    hh: HHService,
    state: FSMContext,
    search: str | None = None,
    excluded: str | None = None,
    message_template: str | None = None,
) -> None:
    status_msg = await message.edit_text(
        "🚀 Рассылка откликов запущена...\n"
        "Это может занять несколько минут."
    )

    async def progress(text: str) -> None:
        try:
            await status_msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await hh.apply_similar(
            user_id,
            callback=progress,
            search=search,
            excluded_terms=excluded,
            message_template=message_template,
        )
    except Exception as ex:
        await status_msg.edit_text(f"❌ Ошибка при рассылке: {ex}")
