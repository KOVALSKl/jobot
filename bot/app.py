"""Фабрика приложения — создаёт и связывает все компоненты бота."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.auth_manager import AuthManager
from bot.config import config
from bot.handlers import apply, auth, negotiations, resumes, start
from bot.middlewares import AccessControlMiddleware
from bot.services import (
    ApiService,
    ApplyService,
    AuthService,
    NegotiationService,
    ResumeService,
)

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    auth_service = AuthService(data_dir=config.data_dir)
    dp["auth_service"] = auth_service
    dp["resume_service"] = ResumeService(data_dir=config.data_dir)
    dp["apply_service"] = ApplyService(data_dir=config.data_dir)
    dp["negotiation_service"] = NegotiationService(data_dir=config.data_dir)
    dp["api_service"] = ApiService(data_dir=config.data_dir)
    dp["auth_manager"] = AuthManager(auth_service=auth_service)

    dp.message.middleware(AccessControlMiddleware())
    dp.callback_query.middleware(AccessControlMiddleware())

    dp.include_routers(
        start.router,
        auth.router,
        resumes.router,
        apply.router,
        negotiations.router,
    )

    return dp
