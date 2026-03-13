"""Обработчики массового отклика на похожие вакансии."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.decorators import require_auth
from bot.keyboards import (
    apply_confirm,
    apply_exclude_mode,
    apply_options,
    apply_partial_risk_confirm,
    cancel_kb,
)
from bot.services.auth import AuthService
from bot.services.heavy_executor import TaskCancelledError, run_heavy_operation
from bot.services.heavy_queue import format_queue_error, schedule_heavy_task
from bot.services.vacancy_filter import has_short_excluded_terms, parse_excluded_terms
from bot.states import ApplyStates
from bot.settings import HEAVY_TASKS_MODE
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
    callback: CallbackQuery
) -> None:
    """Запускает отклик с настройками по умолчанию (без поискового фильтра)."""
    await callback.answer()
    await _run_apply(callback.message, callback.from_user.id)


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
    """Сохраняет исключающие термины и переводит на выбор режима фильтрации."""
    excluded = (
        message.text.strip() if message.text.strip() != "-" else None
    )
    await state.update_data(excluded=excluded)
    await state.set_state(ApplyStates.waiting_for_exclude_mode)
    await message.answer(
        t("apply.exclude_mode_prompt"),
        parse_mode="HTML",
        reply_markup=apply_exclude_mode(),
    )


@router.callback_query(
    F.data.in_({"apply_mode_default_safe", "apply_mode_partial_aggressive"})
)
async def apply_mode_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет режим фильтрации и при необходимости запрашивает подтверждение риска."""
    await callback.answer()
    mode = (
        "partial_aggressive"
        if callback.data == "apply_mode_partial_aggressive"
        else "default_safe"
    )
    await state.update_data(exclude_mode=mode)
    data = await state.get_data()
    excluded_terms = parse_excluded_terms(data.get("excluded"))

    if mode == "partial_aggressive" and has_short_excluded_terms(excluded_terms):
        risky_terms = ", ".join(term for term in excluded_terms if len(term) <= 1)
        await state.set_state(ApplyStates.waiting_for_partial_confirm)
        await callback.message.edit_text(
            t("apply.partial_short_terms_warning", terms=risky_terms),
            parse_mode="HTML",
            reply_markup=apply_partial_risk_confirm(),
        )
        return

    await _ask_message_template(callback.message, state)


@router.callback_query(F.data == "apply_partial_risk_back")
async def apply_partial_risk_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает пользователя к выбору режима фильтрации."""
    await callback.answer()
    await state.set_state(ApplyStates.waiting_for_exclude_mode)
    await callback.message.edit_text(
        t("apply.exclude_mode_prompt"),
        parse_mode="HTML",
        reply_markup=apply_exclude_mode(),
    )


@router.callback_query(F.data == "apply_partial_risk_yes")
async def apply_partial_risk_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждает риск partial-режима и переходит к вводу письма."""
    await callback.answer()
    await _ask_message_template(callback.message, state)


async def _ask_message_template(message: Message, state: FSMContext) -> None:
    await state.set_state(ApplyStates.waiting_for_message)
    await message.edit_text(
        t("apply.message_prompt"),
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ApplyStates.waiting_for_message)
async def apply_message_received(
    message: Message, state: FSMContext
) -> None:
    """Сохраняет шаблон сопроводительного письма и отображает сводку для подтверждения."""
    msg_template = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(message_template=msg_template)
    data = await state.get_data()
    search = data.get("search")
    excluded = data.get("excluded")
    exclude_mode = data.get("exclude_mode") or "default_safe"
    mode_label = t(f"apply.mode_label_{exclude_mode}")

    summary_parts = ["<b>Параметры рассылки:</b>"]
    summary_parts.append(f"🔍 Поиск: {search or 'все подходящие'}")
    summary_parts.append(f"🚫 Исключения: {excluded or 'нет'}")
    summary_parts.append(f"🎛 Режим исключений: {mode_label}")
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
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Подтверждает и запускает процесс отклика."""
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    await _run_apply(
        callback.message,
        callback.from_user.id,
        search=data.get("search"),
        excluded=data.get("excluded"),
        exclude_mode=data.get("exclude_mode"),
        message_template=data.get("message_template"),
    )


async def _run_apply(
    message: Message,
    user_id: int,
    search: str | None = None,
    excluded: str | None = None,
    exclude_mode: str | None = None,
    message_template: str | None = None,
) -> None:
    """Выполняет цикл отклика на похожие вакансии и транслирует прогресс."""
    if HEAVY_TASKS_MODE == "celery":
        try:
            task = await schedule_heavy_task(
                user_id=user_id,
                operation="apply",
                payload={
                    "search": search,
                    "excluded_terms": excluded,
                    "exclude_mode": exclude_mode,
                    "message_template": message_template,
                },
            )
        except Exception as ex:
            await message.edit_text(format_queue_error(ex))
            return
        await message.edit_text(
            "✅ Задача поставлена в очередь.\n"
            f"ID: <code>{task.task_id}</code>\n"
            "Проверьте прогресс через /status",
            parse_mode="HTML",
        )
        return

    status_msg = await message.edit_text(t("apply.running"))

    async def progress(text: str) -> None:
        try:
            await status_msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        result = await run_heavy_operation(
            operation="apply",
            payload={
                "user_id": user_id,
                "search": search,
                "excluded_terms": excluded,
                "exclude_mode": exclude_mode,
                "message_template": message_template,
            },
            report_progress=progress,
            is_cancel_requested=lambda: False,
        )
        await status_msg.edit_text(result, parse_mode="HTML")
    except TaskCancelledError as ex:
        await status_msg.edit_text(str(ex))
    except Exception as ex:
        await status_msg.edit_text(t("apply.error", error=ex))
