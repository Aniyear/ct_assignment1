"""Financial tools of the agent.

Finance only: expenses, incomes, accounts, categories, reports.
Every tool returns a structure with an `ok` field so the model cannot present a
failure as a success.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core import notion_client as nc
from core.notion_client import NotionClient
from core.users import UserProfile
from core.workspace import (
    DB_ACCOUNTS,
    DB_CATEGORIES,
    DB_EXPENSES,
    DB_INCOMES,
    FIELDS,
    KIND_EXPENSE,
    KIND_INCOME,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def today_for(profile: UserProfile) -> date:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(profile.timezone)).date()
        except Exception:
            pass
    return datetime.now().date()


def period_range(profile: UserProfile, period: str) -> Tuple[str, str]:
    """Returns (start, end) as YYYY-MM-DD strings."""
    today = today_for(profile)
    period = (period or "month").lower()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "yesterday":
        day = today - timedelta(days=1)
        return day.isoformat(), day.isoformat()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if period == "prev_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1).isoformat(), last_prev.isoformat()
    if period == "year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    return today.replace(day=1).isoformat(), today.isoformat()


class FinanceTools:
    """A Notion wrapper bound to one specific user."""

    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.client = NotionClient(profile.notion_token)

    # ───── helpers ─────

    def _db(self, key: str) -> str:
        return self.profile.databases.get(key, "")

    def _fail(self, message: str) -> Dict[str, Any]:
        return {"ok": False, "error": message}

    def _find_row(self, db_key: str, name: str) -> Optional[Dict[str, Any]]:
        title_field = FIELDS[db_key]["title"]
        result = self.client.query_database(
            self._db(db_key),
            filter_={"property": title_field, "title": {"contains": name}},
            page_size=5,
        )
        if result.get("error"):
            return None
        rows = result.get("results", [])
        return rows[0] if rows else None

    def _rows_in_period(self, db_key: str, start: str, end: str, limit: int = 100) -> List[Dict[str, Any]]:
        date_field = FIELDS[db_key]["date"]
        result = self.client.query_database(
            self._db(db_key),
            filter_={"and": [
                {"property": date_field, "date": {"on_or_after": start}},
                {"property": date_field, "date": {"on_or_before": end}},
            ]},
            sorts=[{"property": date_field, "direction": "descending"}],
            page_size=limit,
        )
        if result.get("error"):
            return []
        return result.get("results", [])

    def _category_name(self, row: Dict[str, Any]) -> str:
        ids = nc.read_relation_ids(row, FIELDS[DB_EXPENSES]["category"])
        if not ids:
            return "Uncategorized"
        page = self.client.retrieve_page(ids[0])
        if page.get("error"):
            return "Uncategorized"
        return nc.read_title(page, FIELDS[DB_CATEGORIES]["title"]) or "Uncategorized"

    def _adjust_balance(self, account_row: Dict[str, Any], delta: float) -> Optional[float]:
        field = FIELDS[DB_ACCOUNTS]["balance"]
        current = nc.read_number(account_row, field) or 0.0
        new_value = round(current + delta, 2)
        result = self.client.update_row(account_row["id"], {field: nc.number_value(new_value)})
        return None if result.get("error") else new_value

    # ───── tools ─────

    def add_account(self, name: str, balance: float = 0.0, currency: str = "") -> Dict[str, Any]:
        fields = FIELDS[DB_ACCOUNTS]
        payload = {
            fields["title"]: nc.title_value(name),
            fields["balance"]: nc.number_value(balance or 0),
            fields["currency"]: nc.text_value(currency or self.profile.currency),
        }
        result = self.client.create_row(self._db(DB_ACCOUNTS), payload)
        if result.get("error"):
            return self._fail(result.get("message", "Could not create the account"))
        return {"ok": True, "account": name, "balance": balance}

    def list_accounts(self) -> Dict[str, Any]:
        result = self.client.query_database(self._db(DB_ACCOUNTS), page_size=50)
        if result.get("error"):
            return self._fail(result.get("message", "Could not read accounts"))
        fields = FIELDS[DB_ACCOUNTS]
        accounts = [
            {
                "name": nc.read_title(row, fields["title"]),
                "balance": nc.read_number(row, fields["balance"]) or 0,
            }
            for row in result.get("results", [])
        ]
        total = round(sum(item["balance"] for item in accounts), 2)
        return {"ok": True, "accounts": accounts, "total": total, "currency": self.profile.currency}

    def list_categories(self, kind: str = "") -> Dict[str, Any]:
        result = self.client.query_database(self._db(DB_CATEGORIES), page_size=100)
        if result.get("error"):
            return self._fail(result.get("message", "Could not read categories"))
        fields = FIELDS[DB_CATEGORIES]
        items = []
        for row in result.get("results", []):
            row_kind = nc.read_select(row, fields["kind"])
            if kind and row_kind != kind:
                continue
            items.append({"name": nc.read_title(row, fields["title"]), "kind": row_kind})
        return {"ok": True, "categories": items}

    def add_category(self, name: str, kind: str = KIND_EXPENSE) -> Dict[str, Any]:
        fields = FIELDS[DB_CATEGORIES]
        result = self.client.create_row(self._db(DB_CATEGORIES), {
            fields["title"]: nc.title_value(name),
            fields["kind"]: nc.select_value(kind if kind in (KIND_EXPENSE, KIND_INCOME) else KIND_EXPENSE),
        })
        if result.get("error"):
            return self._fail(result.get("message", "Could not create the category"))
        return {"ok": True, "category": name, "kind": kind}

    def add_expense(self, amount: float, title: str, category: str = "", account: str = "",
                    when: str = "", notes: str = "") -> Dict[str, Any]:
        fields = FIELDS[DB_EXPENSES]
        when = when or today_for(self.profile).isoformat()
        payload: Dict[str, Any] = {
            fields["title"]: nc.title_value(title or "Expense"),
            fields["amount"]: nc.number_value(amount),
            fields["date"]: nc.date_value(when),
            fields["notes"]: nc.text_value(notes),
        }

        warnings: List[str] = []
        if category:
            row = self._find_row(DB_CATEGORIES, category)
            if row:
                payload[fields["category"]] = nc.relation_value(row["id"])
            else:
                warnings.append(f"Category '{category}' not found, saved without a category")

        account_row = None
        if account:
            account_row = self._find_row(DB_ACCOUNTS, account)
            if account_row:
                payload[fields["account"]] = nc.relation_value(account_row["id"])
            else:
                warnings.append(f"Account '{account}' not found, balance unchanged")

        result = self.client.create_row(self._db(DB_EXPENSES), payload)
        if result.get("error"):
            return self._fail(result.get("message", "Could not save the expense"))

        new_balance = None
        if account_row:
            new_balance = self._adjust_balance(account_row, -abs(float(amount)))
            if new_balance is None:
                warnings.append("Row created, but the account balance could not be updated")

        return {
            "ok": True,
            "saved": {"title": title, "amount": amount, "date": when,
                      "category": category or None, "account": account or None},
            "account_balance": new_balance,
            "warnings": warnings,
        }

    def add_income(self, amount: float, source: str, account: str = "", when: str = "",
                   notes: str = "") -> Dict[str, Any]:
        fields = FIELDS[DB_INCOMES]
        when = when or today_for(self.profile).isoformat()
        payload: Dict[str, Any] = {
            fields["title"]: nc.title_value(source or "Income"),
            fields["amount"]: nc.number_value(amount),
            fields["date"]: nc.date_value(when),
            fields["notes"]: nc.text_value(notes),
        }

        warnings: List[str] = []
        account_row = None
        if account:
            account_row = self._find_row(DB_ACCOUNTS, account)
            if account_row:
                payload[fields["account"]] = nc.relation_value(account_row["id"])
            else:
                warnings.append(f"Account '{account}' not found, balance unchanged")

        result = self.client.create_row(self._db(DB_INCOMES), payload)
        if result.get("error"):
            return self._fail(result.get("message", "Could not save the income"))

        new_balance = None
        if account_row:
            new_balance = self._adjust_balance(account_row, abs(float(amount)))
            if new_balance is None:
                warnings.append("Row created, but the account balance could not be updated")

        return {
            "ok": True,
            "saved": {"source": source, "amount": amount, "date": when, "account": account or None},
            "account_balance": new_balance,
            "warnings": warnings,
        }

    def list_transactions(self, kind: str = "expenses", period: str = "month",
                          limit: int = 15) -> Dict[str, Any]:
        db_key = DB_INCOMES if kind == "incomes" else DB_EXPENSES
        fields = FIELDS[db_key]
        start, end = period_range(self.profile, period)
        rows = self._rows_in_period(db_key, start, end, limit=min(limit, 50))
        items = []
        for row in rows:
            item = {
                "name": nc.read_title(row, fields["title"]),
                "amount": nc.read_number(row, fields["amount"]) or 0,
                "date": nc.read_date(row, fields["date"]),
            }
            if db_key == DB_EXPENSES:
                item["category"] = self._category_name(row)
            items.append(item)
        return {"ok": True, "period": f"{start}…{end}", "kind": kind, "items": items,
                "currency": self.profile.currency}

    def summary(self, period: str = "month") -> Dict[str, Any]:
        start, end = period_range(self.profile, period)

        expense_rows = self._rows_in_period(DB_EXPENSES, start, end)
        income_rows = self._rows_in_period(DB_INCOMES, start, end)

        e_fields = FIELDS[DB_EXPENSES]
        i_fields = FIELDS[DB_INCOMES]

        spent = round(sum(nc.read_number(row, e_fields["amount"]) or 0 for row in expense_rows), 2)
        earned = round(sum(nc.read_number(row, i_fields["amount"]) or 0 for row in income_rows), 2)

        by_category: Dict[str, float] = {}
        for row in expense_rows:
            name = self._category_name(row)
            by_category[name] = round(
                by_category.get(name, 0) + (nc.read_number(row, e_fields["amount"]) or 0), 2
            )
        top = sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)

        return {
            "ok": True,
            "period": f"{start}…{end}",
            "spent": spent,
            "earned": earned,
            "net": round(earned - spent, 2),
            "expense_count": len(expense_rows),
            "income_count": len(income_rows),
            "by_category": [{"category": name, "amount": value} for name, value in top],
            "currency": self.profile.currency,
        }

    def update_transaction(self, name: str, kind: str = "expenses", new_amount: Optional[float] = None,
                           new_category: str = "", new_title: str = "", new_date: str = "",
                           new_notes: str = "") -> Dict[str, Any]:
        db_key = DB_INCOMES if kind == "incomes" else DB_EXPENSES
        fields = FIELDS[db_key]
        row = self._find_row(db_key, name)
        if not row:
            return self._fail(f"Record '{name}' not found")

        updates: Dict[str, Any] = {}
        if new_amount is not None:
            updates[fields["amount"]] = nc.number_value(new_amount)
        if new_title:
            updates[fields["title"]] = nc.title_value(new_title)
        if new_date:
            updates[fields["date"]] = nc.date_value(new_date)
        if new_notes:
            updates[fields["notes"]] = nc.text_value(new_notes)
        if new_category and db_key == DB_EXPENSES:
            category_row = self._find_row(DB_CATEGORIES, new_category)
            if not category_row:
                return self._fail(f"Category '{new_category}' not found")
            updates[fields["category"]] = nc.relation_value(category_row["id"])

        if not updates:
            return self._fail("Nothing to change was specified")

        result = self.client.update_row(row["id"], updates)
        if result.get("error"):
            return self._fail(result.get("message", "Could not update the record"))
        return {"ok": True, "updated": nc.read_title(row, fields["title"]), "changes": list(updates.keys())}

    def delete_transaction(self, name: str, kind: str = "expenses") -> Dict[str, Any]:
        db_key = DB_INCOMES if kind == "incomes" else DB_EXPENSES
        row = self._find_row(db_key, name)
        if not row:
            return self._fail(f"Record '{name}' not found")
        result = self.client.archive_row(row["id"])
        if result.get("error"):
            return self._fail(result.get("message", "Could not delete the record"))
        return {"ok": True, "deleted": name}

    # ───── dispatcher ─────

    def call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "add_expense": self.add_expense,
            "add_income": self.add_income,
            "add_account": self.add_account,
            "add_category": self.add_category,
            "list_accounts": self.list_accounts,
            "list_categories": self.list_categories,
            "list_transactions": self.list_transactions,
            "summary": self.summary,
            "update_transaction": self.update_transaction,
            "delete_transaction": self.delete_transaction,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return self._fail(f"Unknown tool: {tool_name}")
        try:
            return handler(**arguments)
        except TypeError as exc:
            return self._fail(f"Invalid arguments for {tool_name}: {exc}")
        except Exception as exc:  # no tool error may ever crash the bot
            return self._fail(f"Tool {tool_name} failed: {exc}")


PERIOD_ENUM = ["today", "yesterday", "week", "month", "prev_month", "year"]
KIND_ENUM = [KIND_EXPENSE, KIND_INCOME]

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Save an expense and subtract the amount from an account if one is given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Expense amount"},
                    "title": {"type": "string", "description": "What the money was spent on"},
                    "category": {"type": "string", "description": "Category name from the database"},
                    "account": {"type": "string", "description": "Account name"},
                    "when": {"type": "string", "description": "Date YYYY-MM-DD, defaults to today"},
                    "notes": {"type": "string"},
                },
                "required": ["amount", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_income",
            "description": "Save an income and top up an account if one is given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "source": {"type": "string", "description": "Income source"},
                    "account": {"type": "string"},
                    "when": {"type": "string", "description": "Date YYYY-MM-DD"},
                    "notes": {"type": "string"},
                },
                "required": ["amount", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_account",
            "description": "Create an account (card, cash, deposit) with a starting balance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "balance": {"type": "number"},
                    "currency": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_category",
            "description": "Add a new expense or income category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": KIND_ENUM},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_accounts",
            "description": "Show accounts and balances. Call it before guessing an account name.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_categories",
            "description": "Show the available categories.",
            "parameters": {
                "type": "object",
                "properties": {"kind": {"type": "string", "enum": KIND_ENUM}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_transactions",
            "description": "List transactions for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["expenses", "incomes"]},
                    "period": {"type": "string", "enum": PERIOD_ENUM},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summary",
            "description": "Period summary: total spent, total earned, net and top categories.",
            "parameters": {
                "type": "object",
                "properties": {"period": {"type": "string", "enum": PERIOD_ENUM}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_transaction",
            "description": "Update an existing record found by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Part of the record name"},
                    "kind": {"type": "string", "enum": ["expenses", "incomes"]},
                    "new_amount": {"type": "number"},
                    "new_category": {"type": "string"},
                    "new_title": {"type": "string"},
                    "new_date": {"type": "string"},
                    "new_notes": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_transaction",
            "description": "Delete (archive) a record by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": ["expenses", "incomes"]},
                },
                "required": ["name"],
            },
        },
    },
]
