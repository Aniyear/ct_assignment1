"""Обработчики Telegram.

Порядок регистрации важен: сначала команды, потом кнопки, и только в конце
универсальный текстовый обработчик, иначе он «съест» всё остальное.
"""

import asyncio
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards import BUTTON_PROMPTS, main_keyboard
from bot.texts import HELP, NEED_CONNECT, NEED_SETUP, NOT_ALLOWED, WELCOME
from core.agent import Agent
from core.memory import ConversationMemory
from core.notion_client import NotionClient, normalize_id
from core.tool_log import tool_log
from core.users import UserStore
from core.workspace import TITLES, setup_workspace


def build_router(settings, store: UserStore, agent: Agent, memory: ConversationMemory) -> Router:
    router = Router()

    def profile_for(message: Message):
        return store.get_or_create(
            message.from_user.id, settings.default_currency, settings.timezone
        )

    async def guard(message: Message) -> bool:
        if settings.user_allowed(message.from_user.id):
            return True
        await message.answer(f"{NOT_ALLOWED}\nТвой ID: {message.from_user.id}")
        return False

    # ───── команды ─────

    @router.message(CommandStart())
    async def cmd_start(message: Message):
        if not await guard(message):
            return
        profile = profile_for(message)
        if profile.ready:
            await message.answer(
                "👋 С возвращением! Всё подключено, можно сразу писать траты.",
                reply_markup=main_keyboard(),
            )
        else:
            await message.answer(WELCOME, reply_markup=main_keyboard())

    @router.message(Command("help"))
    async def cmd_help(message: Message):
        if not await guard(message):
            return
        await message.answer(HELP, reply_markup=main_keyboard())

    @router.message(Command("connect"))
    async def cmd_connect(message: Message):
        if not await guard(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await message.answer("Формат: /connect ntn_твой_токен")
            return

        token = parts[1].strip()
        check = await asyncio.to_thread(NotionClient(token).whoami)
        if check.get("error"):
            await message.answer(
                "❌ Токен не подошёл.\n"
                f"Notion ответил: {check.get('message')}\n\n"
                "Проверь, что скопирован Internal Integration Secret целиком."
            )
            return

        profile = profile_for(message)
        profile.notion_token = token
        store.save(profile)

        bot_name = (check.get("name") or "интеграция")
        await message.answer(
            f"✅ Notion подключён ({bot_name}).\n"
            "⚠️ Удали сообщение с токеном из чата.\n\n"
            "Теперь: /setup ссылка_на_страницу_Notion"
        )

    @router.message(Command("setup"))
    async def cmd_setup(message: Message):
        if not await guard(message):
            return
        profile = profile_for(message)
        if not profile.connected:
            await message.answer(NEED_CONNECT)
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await message.answer("Формат: /setup ссылка_на_страницу_Notion")
            return

        page_id = normalize_id(parts[1].strip())
        client = NotionClient(profile.notion_token)

        check = await asyncio.to_thread(client.retrieve_page, page_id)
        if check.get("error"):
            await message.answer(
                "❌ Не вижу эту страницу.\n"
                f"Notion ответил: {check.get('message')}\n\n"
                "Скорее всего не выдан доступ: открой страницу → «…» → Connections → выбери свою интеграцию."
            )
            return

        await message.answer("⏳ Создаю базы, это займёт около минуты…")
        databases, problems = await asyncio.to_thread(setup_workspace, client, page_id)

        profile.page_id = page_id
        profile.databases = databases
        store.save(profile)

        created = "\n".join(f"• {TITLES[key][1]} {TITLES[key][0]}" for key in databases)
        text = f"✅ Готово. Создано баз: {len(databases)}\n{created}"
        if problems:
            text += "\n\n⚠️ Были проблемы:\n" + "\n".join(f"• {item}" for item in problems[:5])
        if profile.ready:
            text += "\n\nПопробуй: «добавь счёт Карта с балансом 100000»"
        await message.answer(text, reply_markup=main_keyboard())

    @router.message(Command("status"))
    async def cmd_status(message: Message):
        if not await guard(message):
            return
        profile = profile_for(message)
        stats = tool_log.stats(profile.user_id)
        lines = [
            "🧠 Состояние агента",
            "",
            f"• Notion: {'подключён ' + profile.masked_token() if profile.connected else 'не подключён'}",
            f"• Баз настроено: {len(profile.databases)} из 4",
            f"• Валюта: {profile.currency}, пояс: {profile.timezone}",
            f"• Память диалога: {memory.size(profile.user_id)} реплик",
            f"• Модель: {settings.llm_model}",
            "",
            f"• Вызовов инструментов: {stats['calls']}, из них ошибок: {stats['errors']}",
            f"• Среднее время инструмента: {stats['avg_ms']} мс",
        ]
        if stats["top"]:
            top = ", ".join(f"{name} ({count})" for name, count in stats["top"])
            lines.append(f"• Чаще всего: {top}")
        if not profile.connected:
            lines += ["", NEED_CONNECT]
        elif not profile.ready:
            lines += ["", NEED_SETUP]
        await message.answer("\n".join(lines))

    @router.message(Command("trace"))
    async def cmd_trace(message: Message):
        if not await guard(message):
            return
        entries = tool_log.recent(message.from_user.id, limit=10)
        if not entries:
            await message.answer("📜 Пока ни одного вызова инструментов.")
            return
        lines = ["📜 Последние действия", ""]
        for entry in entries:
            mark = "✅" if entry["ok"] else "❌"
            lines.append(f"{mark} {entry['time']} • {entry['tool']} • {entry['duration_ms']} мс")
        await message.answer("\n".join(lines))

    @router.message(Command("forget"))
    async def cmd_forget(message: Message):
        if not await guard(message):
            return
        memory.clear(message.from_user.id)
        await message.answer("🧹 Контекст диалога очищен. Данные в Notion не тронуты.")

    @router.message(Command("disconnect"))
    async def cmd_disconnect(message: Message):
        if not await guard(message):
            return
        memory.clear(message.from_user.id)
        removed = store.delete(message.from_user.id)
        await message.answer(
            "🗑 Профиль удалён, токен больше не хранится. Базы в Notion остались на месте."
            if removed else "Профиля и так не было."
        )

    # ───── свободный текст и кнопки ─────

    @router.message(F.text)
    async def on_text(message: Message):
        if not await guard(message):
            return
        profile = profile_for(message)
        if not profile.connected:
            await message.answer(NEED_CONNECT)
            return
        if not profile.ready:
            await message.answer(NEED_SETUP)
            return

        user_text = BUTTON_PROMPTS.get(message.text, message.text)
        await message.bot.send_chat_action(message.chat.id, "typing")

        started = datetime.now()
        history = memory.history(profile.user_id)
        reply, used_tools = await asyncio.to_thread(agent.respond, profile, history, user_text)
        elapsed = (datetime.now() - started).total_seconds()

        memory.add(profile.user_id, "user", user_text)
        memory.add(profile.user_id, "assistant", reply)

        print(f"[agent] user={profile.user_id} tools={used_tools} {elapsed:.1f}s")
        await message.answer(reply, reply_markup=main_keyboard())

    return router
