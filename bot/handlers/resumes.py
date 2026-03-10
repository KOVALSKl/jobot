"""Обработчики получения списка и обновления резюме HH."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.decorators import require_auth
from bot.keyboards import resume_actions
from bot.services.auth import AuthService
from bot.services.heavy_executor import TaskCancelledError, run_heavy_operation
from bot.services.heavy_queue import format_queue_error, schedule_heavy_task
from bot.services.resume import ResumeService
from bot.settings import HEAVY_TASKS_MODE
from bot.texts import t

router = Router()


@router.message(Command("resumes"))
@router.message(F.text == "📄 Мои резюме")
@require_auth
async def cmd_resumes(message: Message, auth_service: AuthService, resume_service: ResumeService) -> None:
    """Отображает все резюме пользователя из HH."""
    wait_msg = await message.answer(t("resumes.loading"))
    try:
        text = await resume_service.list_resumes(message.from_user.id)
        await wait_msg.edit_text(
            text, reply_markup=resume_actions(), parse_mode="HTML"
        )
    except Exception as ex:
        await wait_msg.edit_text(t("common.error", error=ex))


@router.message(Command("update"))
@router.callback_query(F.data == "update_resumes")
@require_auth
async def cmd_update_resumes(
    event: Message | CallbackQuery, auth_service: AuthService
) -> None:
    """Публикует / поднимает все доступные для обновления резюме."""
    user_id = event.from_user.id

    if HEAVY_TASKS_MODE == "celery":
        if isinstance(event, CallbackQuery):
            await event.answer()
            sender = event.message
        else:
            sender = event
        try:
            task = await schedule_heavy_task(
                user_id=user_id,
                operation="update",
                payload={},
            )
        except Exception as ex:
            await sender.answer(format_queue_error(ex))
            return
        await sender.answer(
            "✅ Обновление резюме поставлено в очередь.\n"
            f"ID: <code>{task.task_id}</code>\n"
            "Проверьте прогресс через /status",
            parse_mode="HTML",
        )
        return

    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = await event.message.edit_text(t("resumes.updating"))
    else:
        msg = await event.answer(t("resumes.updating"))

    async def progress(text: str) -> None:
        try:
            await msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        result = await run_heavy_operation(
            operation="update",
            payload={"user_id": user_id},
            report_progress=progress,
            is_cancel_requested=lambda: False,
        )
        await msg.edit_text(result, parse_mode="HTML")
    except TaskCancelledError as ex:
        await msg.edit_text(str(ex))
    except Exception as ex:
        await msg.edit_text(t("common.error", error=ex))
