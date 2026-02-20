from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.auth_manager import AuthManager
from bot.config import config
from bot.handlers import apply, auth, negotiations, resumes, start
from bot.hh_service import HHService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    hh = HHService(data_dir=config.data_dir)
    auth_manager = AuthManager(hh_service=hh)

    dp.include_routers(
        start.router,
        auth.router,
        resumes.router,
        apply.router,
        negotiations.router,
    )

    dp["hh"] = hh
    dp["auth"] = auth_manager

    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
