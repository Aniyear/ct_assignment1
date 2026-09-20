"""User profiles.

This module is what makes the bot multi-tenant: every user has their own Notion token
and their own database ids. In a personal single-user bot these values were hard-coded
in environment variables.

Storage is a JSON file: simple and transparent for an academic project. On an ephemeral
disk (Render) point USERS_FILE at a mounted Disk, otherwise profiles are wiped on deploy.
"""

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class UserProfile:
    user_id: int
    notion_token: str = ""
    page_id: str = ""
    databases: Dict[str, str] = field(default_factory=dict)
    currency: str = "KZT"
    timezone: str = "Asia/Almaty"
    created_at: str = ""

    @property
    def connected(self) -> bool:
        return bool(self.notion_token)

    @property
    def ready(self) -> bool:
        """Ready only when both the token and all four databases are present."""
        needed = ("expenses", "incomes", "accounts", "categories")
        return self.connected and all(self.databases.get(key) for key in needed)

    def masked_token(self) -> str:
        if not self.notion_token:
            return "not set"
        return f"{self.notion_token[:7]}…{self.notion_token[-4:]}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            user_id=int(data.get("user_id", 0)),
            notion_token=data.get("notion_token", ""),
            page_id=data.get("page_id", ""),
            databases=dict(data.get("databases", {})),
            currency=data.get("currency", "KZT"),
            timezone=data.get("timezone", "Asia/Almaty"),
            created_at=data.get("created_at", ""),
        )


class UserStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._cache: Dict[str, UserProfile] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self._cache = {
                str(key): UserProfile.from_dict(value) for key, value in raw.items()
            }
            print(f"[UserStore] Profiles loaded: {len(self._cache)}")
        except Exception as exc:
            print(f"[UserStore] Could not read {self.path}: {exc}")

    def _flush(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {key: profile.to_dict() for key, profile in self._cache.items()}
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def get(self, user_id: int) -> Optional[UserProfile]:
        return self._cache.get(str(user_id))

    def get_or_create(self, user_id: int, currency: str, timezone: str) -> UserProfile:
        existing = self.get(user_id)
        if existing:
            return existing
        profile = UserProfile(
            user_id=user_id,
            currency=currency,
            timezone=timezone,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        with self._lock:
            self._cache[str(user_id)] = profile
            self._flush()
        return profile

    def save(self, profile: UserProfile) -> None:
        with self._lock:
            self._cache[str(profile.user_id)] = profile
            self._flush()

    def delete(self, user_id: int) -> bool:
        with self._lock:
            removed = self._cache.pop(str(user_id), None) is not None
            if removed:
                self._flush()
        return removed

    def count(self) -> int:
        return len(self._cache)
