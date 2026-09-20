"""Thin Notion API client.

Difference from a personal single-user bot: the client is created PER USER with
their own integration token instead of one global client for the whole service.

Errors are never swallowed silently: the client returns {"error": True, ...} so the
model can see the failure and cannot present an intention as a result.
"""

import re
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2022-06-28"

_UUID_RE = re.compile(r"([0-9a-fA-F]{32})")
_DASHED_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def normalize_id(raw: str) -> str:
    """Accepts a page URL or a bare id and returns a dashed UUID."""
    text = (raw or "").strip()
    dashed = _DASHED_RE.search(text)
    if dashed:
        return dashed.group(1).lower()
    plain = _UUID_RE.findall(text.replace("-", ""))
    if plain:
        value = plain[-1].lower()
        return f"{value[0:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:32]}"
    return text


class NotionClient:
    def __init__(self, token: str, timeout: int = 20):
        self.token = (token or "").strip()
        self.timeout = timeout

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": API_VERSION,
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{API_BASE}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method.upper(), url, headers=self.headers, json=payload, timeout=self.timeout
            )
        except Exception as exc:
            return {"error": True, "code": "network", "message": f"Network unavailable: {exc}"}

        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("message", response.text[:300])
                code = body.get("code", str(response.status_code))
            except Exception:
                message, code = response.text[:300], str(response.status_code)
            return {"error": True, "code": code, "status": response.status_code, "message": message}

        try:
            return response.json()
        except Exception:
            return {"error": True, "code": "bad_json", "message": "Notion returned a non-JSON body"}

    # ───── basic operations ─────

    def whoami(self) -> Dict[str, Any]:
        return self.request("GET", "users/me")

    def retrieve_page(self, page_id: str) -> Dict[str, Any]:
        return self.request("GET", f"pages/{normalize_id(page_id)}")

    def create_database(self, parent_page_id: str, title: str, properties: Dict[str, Any],
                        icon: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": normalize_id(parent_page_id)},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        if icon:
            payload["icon"] = {"type": "emoji", "emoji": icon}
        return self.request("POST", "databases", payload)

    def query_database(self, database_id: str, filter_: Optional[Dict[str, Any]] = None,
                       sorts: Optional[List[Dict[str, Any]]] = None, page_size: int = 50) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"page_size": min(100, max(1, page_size))}
        if filter_:
            payload["filter"] = filter_
        if sorts:
            payload["sorts"] = sorts
        return self.request("POST", f"databases/{normalize_id(database_id)}/query", payload)

    def create_row(self, database_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "pages", {
            "parent": {"type": "database_id", "database_id": normalize_id(database_id)},
            "properties": properties,
        })

    def update_row(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("PATCH", f"pages/{normalize_id(page_id)}", {"properties": properties})

    def archive_row(self, page_id: str) -> Dict[str, Any]:
        return self.request("PATCH", f"pages/{normalize_id(page_id)}", {"archived": True})


# ───── reading property values ─────

def read_title(page: Dict[str, Any], name: str) -> str:
    parts = ((page.get("properties", {}).get(name) or {}).get("title")) or []
    return "".join(p.get("plain_text", "") for p in parts).strip()


def read_text(page: Dict[str, Any], name: str) -> str:
    parts = ((page.get("properties", {}).get(name) or {}).get("rich_text")) or []
    return "".join(p.get("plain_text", "") for p in parts).strip()


def read_number(page: Dict[str, Any], name: str) -> Optional[float]:
    return (page.get("properties", {}).get(name) or {}).get("number")


def read_select(page: Dict[str, Any], name: str) -> str:
    option = (page.get("properties", {}).get(name) or {}).get("select") or {}
    return option.get("name", "")


def read_date(page: Dict[str, Any], name: str) -> str:
    value = (page.get("properties", {}).get(name) or {}).get("date") or {}
    return value.get("start") or ""


def read_relation_ids(page: Dict[str, Any], name: str) -> List[str]:
    items = ((page.get("properties", {}).get(name) or {}).get("relation")) or []
    return [item.get("id", "") for item in items if item.get("id")]


# ───── building property values ─────

def title_value(text: str) -> Dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": str(text)[:2000]}}]}


def text_value(text: str) -> Dict[str, Any]:
    if not text:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": str(text)[:2000]}}]}


def number_value(value: float) -> Dict[str, Any]:
    return {"number": float(value)}


def select_value(name: str) -> Dict[str, Any]:
    return {"select": {"name": str(name)}} if name else {"select": None}


def date_value(iso_date: str) -> Dict[str, Any]:
    return {"date": {"start": iso_date}} if iso_date else {"date": None}


def relation_value(page_id: str) -> Dict[str, Any]:
    return {"relation": [{"id": normalize_id(page_id)}]} if page_id else {"relation": []}
