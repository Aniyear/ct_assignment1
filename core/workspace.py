"""Notion workspace template.

The /setup command creates four databases on the user's page. The user does not need
to know the schema or any IDs: they only provide a link to an empty page.

Order matters: Accounts and Categories first, then Expenses and Incomes, because the
latter need existing database ids for their relation properties.
"""

from typing import Any, Dict, List, Tuple

from core.notion_client import NotionClient, select_value, title_value

DB_EXPENSES = "expenses"
DB_INCOMES = "incomes"
DB_ACCOUNTS = "accounts"
DB_CATEGORIES = "categories"

KIND_EXPENSE = "expense"
KIND_INCOME = "income"

TITLES = {
    DB_EXPENSES: ("Finance — Expenses", "💸"),
    DB_INCOMES: ("Finance — Incomes", "💰"),
    DB_ACCOUNTS: ("Finance — Accounts", "🏦"),
    DB_CATEGORIES: ("Finance — Categories", "🏷"),
}

# Property names in a single place: rename columns here only.
FIELDS = {
    DB_EXPENSES: {
        "title": "Name",
        "amount": "Amount",
        "date": "Date",
        "notes": "Notes",
        "category": "Category",
        "account": "Account",
    },
    DB_INCOMES: {
        "title": "Source",
        "amount": "Amount",
        "date": "Date",
        "notes": "Notes",
        "account": "Account",
    },
    DB_ACCOUNTS: {
        "title": "Name",
        "balance": "Balance",
        "currency": "Currency",
    },
    DB_CATEGORIES: {
        "title": "Name",
        "kind": "Kind",
    },
}

DEFAULT_EXPENSE_CATEGORIES = [
    "Groceries",
    "Cafes and restaurants",
    "Transport",
    "Housing and utilities",
    "Mobile and internet",
    "Health",
    "Clothing",
    "Entertainment",
    "Subscriptions",
    "Education",
    "Other",
]

DEFAULT_INCOME_CATEGORIES = ["Salary", "Freelance", "Gift", "Other income"]


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
                    {"name": KIND_EXPENSE, "color": "red"},
                    {"name": KIND_INCOME, "color": "green"},
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
    """Creates the four databases and seeds default categories.

    Returns (database id map, list of problems). Partial success stays visible
    instead of being masked as success.
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
            problems.append("Default categories were not created")

    return databases, problems


def seed_categories(client: NotionClient, categories_db: str) -> Tuple[int, List[str]]:
    f = FIELDS[DB_CATEGORIES]
    created = 0
    problems: List[str] = []
    pairs = [(name, KIND_EXPENSE) for name in DEFAULT_EXPENSE_CATEGORIES]
    pairs += [(name, KIND_INCOME) for name in DEFAULT_INCOME_CATEGORIES]

    for name, kind in pairs:
        result = client.create_row(categories_db, {
            f["title"]: title_value(name),
            f["kind"]: select_value(kind),
        })
        if result.get("error"):
            problems.append(f"Category '{name}': {result.get('message')}")
        else:
            created += 1
    return created, problems
