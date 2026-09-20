"""Entry point.

Runs two things in parallel:
1. The Telegram bot (long polling)
2. A tiny HTTP server for health checks, without which Render treats the service as down.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiohttp import web

from bot.handlers import build_router
from config.settings import settings
from core.agent import Agent
from core.memory import ConversationMemory
from core.users import UserStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def run_web(store: UserStore) -> None:
    async def health(_request):
        return web.json_response({
            "status": "ok",
            "service": "personal-cfo-agent",
            "users": store.count(),
            "model": settings.llm_model,
        })

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.port)
    await site.start()
    logging.info("HTTP health check on port %s", settings.port)


async def main() -> None:
    gaps = settings.missing()
    if gaps:
        raise SystemExit(
            "Required environment variables are missing: "
            + ", ".join(gaps)
            + ". Copy .env.example to .env and fill them in."
        )

    store = UserStore(settings.users_file)
    memory = ConversationMemory()
    agent = Agent(settings)

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(settings, store, agent, memory))

    await run_web(store)
    logging.info("Bot started. Stored profiles: %s", store.count())
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        logging.info("Shutting down: %s", exc)
