"""Шаблон рабочего пространства Notion.

Команда /setup создаёт четыре базы на странице пользователя. Пользователю не нужно
знать ни схему, ни ID — он даёт только ссылку на пустую страницу.

Порядок важен: сначала Счета и Категории, потом Расходы и Доходы — им нужны
готовые database_id для relation-связей.
"""

from typing import Any, Dict, List, Tuple

from core.notion_client import NotionClient, select_value, title_value

DB_EXPENSES = "expenses"
DB_INCOMES = "incomes"
DB_ACCOUNTS = "accounts"
DB_CATEGORIES = "categories"

TITLES = {
    DB_EXPENSES: ("Финансы — Расходы", "💸"),
    DB_INCOMES: ("Финансы — Доходы", "💰"),
    DB_ACCOUNTS: ("Финансы — Счета", "🏦"),
    DB_CATEGORIES: ("Финансы — Категории", "🏷"),
}

# Имена свойств в одном месте: если захочешь переименовать колонки — правь только здесь.
FIELDS = {
    DB_EXPENSES: {
        "title": "Название",
        "amount": "Сумма",
        "date": "Дата",
        "notes": "Заметки",
        "category": "Категория",
        "account": "Счёт",
    },
    DB_INCOMES: {
        "title": "Источник",
        "amount": "Сумма",
        "date": "Дата",
        "notes": "Заметки",
        "account": "Счёт",
    },
    DB_ACCOUNTS: {
        "title": "Название",
        "balance": "Баланс",
        "currency": "Валюта",
    },
    DB_CATEGORIES: {
        "title": "Название",
        "kind": "Тип",
    },
}

DEFAULT_EXPENSE_CATEGORIES = [
    "Продукты",
    "Кафе и рестораны",
    "Транспорт",
    "Жильё и коммуналка",
    "Связь и интернет",
    "Здоровье",
    "Одежда",
    "Развлечения",
    "Подписки",
    "Образование",
    "Прочее",
]

DEFAULT_INCOME_CATEGORIES = ["Зарплата", "Подработка", "Подарок", "Прочее"]


def _accounts_schema() -> Dict[str, Any]:
    f = FIELDS[DB_ACCOUNTS]
    return {
        f["title"]: {"title": {}},
        f["balance"]: {"number": {"format": "number"}},
        f["currency"]: {"rich_text": {}},
    }


def _categories_schema() -> Dict[str, Any]:
    f = FIELDS[DB_CATEGORIES]
    return {
        f["title"]: {"title": {}},
        f["kind"]: {
            "select": {
                "options": [
                    {"name": "расход", "color": "red"},
                    {"name": "доход", "color": "green"},
                ]
            }
        },
    }


def _expenses_schema(categories_db: str, accounts_db: str) -> Dict[str, Any]:
    f = FIELDS[DB_EXPENSES]
    return {
        f["title"]: {"title": {}},
        f["amount"]: {"number": {"format": "number"}},
        f["date"]: {"date": {}},
        f["notes"]: {"rich_text": {}},
        f["category"]: {"relation": {"database_id": categories_db, "single_property": {}}},
        f["account"]: {"relation": {"database_id": accounts_db, "single_property": {}}},
    }


def _incomes_schema(accounts_db: str) -> Dict[str, Any]:
    f = FIELDS[DB_INCOMES]
    return {
        f["title"]: {"title": {}},
        f["amount"]: {"number": {"format": "number"}},
        f["date"]: {"date": {}},
        f["notes"]: {"rich_text": {}},
        f["account"]: {"relation": {"database_id": accounts_db, "single_property": {}}},
    }


def setup_workspace(client: NotionClient, parent_page_id: str) -> Tuple[Dict[str, str], List[str]]:
    """Создаёт четыре базы и сеит категории.

    Возвращает (словарь ID баз, список ошибок). Частичный успех виден явно,
    а не маскируется под успех.
    """
    databases: Dict[str, str] = {}
    problems: List[str] = []

    for key, schema in ((DB_ACCOUNTS, _accounts_schema()), (DB_CATEGORIES, _categories_schema())):
        title, icon = TITLES[key]
        result = client.create_database(parent_page_id, title, schema, icon)
        if result.get("error"):
            problems.append(f"{title}: {result.get('message')}")
        else:
            databases[key] = result.get("id", "")

    if DB_CATEGORIES in databases and DB_ACCOUNTS in databases:
        title, icon = TITLES[DB_EXPENSES]
        result = client.create_database(
            parent_page_id, title, _expenses_schema(databases[DB_CATEGORIES], databases[DB_ACCOUNTS]), icon
        )
        if result.get("error"):
            problems.append(f"{title}: {result.get('message')}")
        else:
            databases[DB_EXPENSES] = result.get("id", "")

        title, icon = TITLES[DB_INCOMES]
        result = client.create_database(parent_page_id, title, _incomes_schema(databases[DB_ACCOUNTS]), icon)
        if result.get("error"):
            problems.append(f"{title}: {result.get('message')}")
        else:
            databases[DB_INCOMES] = result.get("id", "")

    if DB_CATEGORIES in databases:
        seeded, seed_problems = seed_categories(client, databases[DB_CATEGORIES])
        problems.extend(seed_problems)
        if seeded == 0 and not seed_problems:
            problems.append("Категории по умолчанию не созданы")

    return databases, problems


def seed_categories(client: NotionClient, categories_db: str) -> Tuple[int, List[str]]:
    f = FIELDS[DB_CATEGORIES]
    created = 0
    problems: List[str] = []
    pairs = [(name, "расход") for name in DEFAULT_EXPENSE_CATEGORIES]
    pairs += [(name, "доход") for name in DEFAULT_INCOME_CATEGORIES]

    for name, kind in pairs:
        result = client.create_row(categories_db, {
            f["title"]: title_value(name),
            f["kind"]: select_value(kind),
        })
        if result.get("error"):
            problems.append(f"Категория '{name}': {result.get('message')}")
        else:
            created += 1
    return created, problems
