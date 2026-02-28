"""Обработчики массового отклика на похожие вакансии."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.decorators import require_auth
from bot.keyboards import apply_confirm, apply_options, cancel_kb
from bot.services.apply import ApplyService
from bot.services.auth import AuthService
from bot.states import ApplyStates
from bot.texts import t

router = Router()


@router.message(Command("apply"))
@router.message(F.text == "🚀 Рассылка откликов")
@require_auth
async def cmd_apply(message: Message, auth_service: AuthService, state: FSMContext) -> None:
    """Отображает меню выбора режима отклика."""
    await state.clear()
    await message.answer(
        t("apply.start_prompt"),
        reply_markup=apply_options(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "apply_default")
async def apply_default(
    callback: CallbackQuery, apply_service: ApplyService, state: FSMContext
) -> None:
    """Запускает отклик с настройками по умолчанию (без поискового фильтра)."""
    await callback.answer()
    await _run_apply(callback.message, callback.from_user.id, apply_service, state)


@router.callback_query(F.data == "apply_search")
async def apply_search_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Запрашивает поисковый запрос для вакансий."""
    await callback.answer()
    await state.set_state(ApplyStates.waiting_for_search)
    await callback.message.edit_text(
        t("apply.search_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_search)
async def apply_search_received(message: Message, state: FSMContext) -> None:
    """Сохраняет поисковый запрос и запрашивает исключающие термины."""
    search = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(search=search)
    await state.set_state(ApplyStates.waiting_for_excluded)
    await message.answer(
        t("apply.excluded_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_excluded)
async def apply_excluded_received(message: Message, state: FSMContext) -> None:
    """Сохраняет исключающие термины и запрашивает шаблон сопроводительного письма."""
    excluded = (
        message.text.strip() if message.text.strip() != "-" else None
    )
    await state.update_data(excluded=excluded)
    await state.set_state(ApplyStates.waiting_for_message)
    await message.answer(
        t("apply.message_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_message)
async def apply_message_received(
    message: Message, state: FSMContext, apply_service: ApplyService
) -> None:
    """Сохраняет шаблон сопроводительного письма и отображает сводку для подтверждения."""
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
    callback: CallbackQuery, apply_service: ApplyService, state: FSMContext
) -> None:
    """Подтверждает и запускает процесс отклика."""
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    await _run_apply(
        callback.message,
        callback.from_user.id,
        apply_service,
        state,
        search=data.get("search"),
        excluded=data.get("excluded"),
        message_template=data.get("message_template"),
    )


async def _run_apply(
    message: Message,
    user_id: int,
    apply_service: ApplyService,
    state: FSMContext,
    search: str | None = None,
    excluded: str | None = None,
    message_template: str | None = None,
) -> None:
    """Выполняет цикл отклика на похожие вакансии и транслирует прогресс."""
    status_msg = await message.edit_text(t("apply.running"))

    async def progress(text: str) -> None:
        try:
            await status_msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        await apply_service.apply_similar(
            user_id,
            callback=progress,
            search=search,
            excluded_terms=excluded,
            message_template=message_template,
        )
    except Exception as ex:
        await status_msg.edit_text(t("apply.error", error=ex))
