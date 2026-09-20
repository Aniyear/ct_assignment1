"""Точка входа.

Запускает две вещи параллельно:
1. Telegram-бота (long polling)
2. Маленький HTTP-сервер для health-check — без него Render считает сервис упавшим.
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
    logging.info("HTTP health-check на порту %s", settings.port)


async def main() -> None:
    gaps = settings.missing()
    if gaps:
        raise SystemExit(
            "Не заполнены обязательные переменные окружения: "
            + ", ".join(gaps)
            + ". Скопируй .env.example в .env и заполни их."
        )

    store = UserStore(settings.users_file)
    memory = ConversationMemory()
    agent = Agent(settings)

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(settings, store, agent, memory))

    await run_web(store)
    logging.info("Бот запущен. Профилей в базе: %s", store.count())
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        logging.info("Остановка: %s", exc)
