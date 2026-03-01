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
from bot.settings import create_storage

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    store = create_storage()

    auth_service = AuthService(storage=store)
    dp["auth_service"] = auth_service
    dp["resume_service"] = ResumeService(storage=store)
    dp["apply_service"] = ApplyService(storage=store)
    dp["negotiation_service"] = NegotiationService(storage=store)
    dp["api_service"] = ApiService(storage=store)
    dp["auth_manager"] = AuthManager(auth_service=auth_service)
    dp["storage"] = store

    dp.message.middleware(AccessControlMiddleware())
    dp.callback_query.middleware(AccessControlMiddleware())

    dp.include_routers(
        start.router,
        auth.router,
        resumes.router,
        apply.router,
        negotiations.router,
    )

    async def on_startup(bot: Bot) -> None:
        logger.info("Инициализация хранилища...")
        await store.init()

    async def on_shutdown(bot: Bot) -> None:
        logger.info("Закрытие хранилища...")
        await store.close()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp
