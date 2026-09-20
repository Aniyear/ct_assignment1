"""Bot keyboard. Buttons are pre-written prompts sent to the same agent."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_TODAY = "📊 Today"
BTN_WEEK = "📅 Week"
BTN_MONTH = "🗓 Month"
BTN_ACCOUNTS = "🏦 Balances"
BTN_CATEGORIES = "🏷 Categories"
BTN_ADVICE = "💡 Advice"

BUTTON_PROMPTS = {
    BTN_TODAY: "Show the summary for today",
    BTN_WEEK: "Show the summary for this week",
    BTN_MONTH: "Show the summary for this month with a breakdown by category",
    BTN_ACCOUNTS: "Show my accounts and balances",
    BTN_CATEGORIES: "Show the list of categories",
    BTN_ADVICE: "Look at my spending this month and give one concrete tip on where I can save",
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
