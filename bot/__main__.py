from __future__ import annotations

import asyncio
import logging
import sys

from bot.app import create_bot, create_dispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = create_bot()
    dp = create_dispatcher()

    @dp.startup()
    async def on_startup() -> None:
        me = await bot.me()
        logger.info("Bot started: @%s [%s]", me.username, me.id)

    @dp.shutdown()
    async def on_shutdown() -> None:
        logger.info("Bot shutting down...")
        await bot.session.close()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
