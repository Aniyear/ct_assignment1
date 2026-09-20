"""Клавиатура бота. Кнопки — это готовые запросы к тому же агенту."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_TODAY = "📊 Сегодня"
BTN_WEEK = "📅 Неделя"
BTN_MONTH = "🗓 Месяц"
BTN_ACCOUNTS = "🏦 Балансы"
BTN_CATEGORIES = "🏷 Категории"
BTN_ADVICE = "💡 Совет"

BUTTON_PROMPTS = {
    BTN_TODAY: "Покажи сводку за сегодня",
    BTN_WEEK: "Покажи сводку за эту неделю",
    BTN_MONTH: "Покажи сводку за этот месяц с разбивкой по категориям",
    BTN_ACCOUNTS: "Покажи мои счета и балансы",
    BTN_CATEGORIES: "Покажи список категорий",
    BTN_ADVICE: "Посмотри мои траты за месяц и дай один конкретный совет, где можно сэкономить",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_WEEK)],
            [KeyboardButton(text=BTN_MONTH), KeyboardButton(text=BTN_ACCOUNTS)],
            [KeyboardButton(text=BTN_CATEGORIES), KeyboardButton(text=BTN_ADVICE)],
        ],
        resize_keyboard=True,
    )
