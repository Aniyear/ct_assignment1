"""Service-level settings.

Only service-wide values live here: bot token, model key, port.
Per-user data (their Notion token and their database IDs) is DELIBERATELY not here:
it lives in core/users.py. That separation is what makes the bot multi-tenant.
"""

import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # in production the variables may already be in the environment
    pass


def _parse_ids(raw: str) -> List[int]:
    result: List[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return result


@dataclass
class Settings:
    telegram_bot_token: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek/deepseek-chat"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout: int = 60
    max_tool_iterations: int = 6
    users_file: str = "data/users.json"
    allowed_user_ids: List[int] = field(default_factory=list)
    default_currency: str = "KZT"
    timezone: str = "Asia/Almaty"
    port: int = 8080

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            llm_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            llm_model=os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            max_tool_iterations=int(os.getenv("MAX_TOOL_ITERATIONS", "6")),
            users_file=os.getenv("USERS_FILE", "data/users.json"),
            allowed_user_ids=_parse_ids(os.getenv("ALLOWED_USER_IDS", "")),
            default_currency=os.getenv("DEFAULT_CURRENCY", "KZT"),
            timezone=os.getenv("TIMEZONE", "Asia/Almaty"),
            port=int(os.getenv("PORT", "8080")),
        )

    def missing(self) -> List[str]:
        """What is missing for a successful start. Better to say it now than crash later."""
        gaps = []
        if not self.telegram_bot_token:
            gaps.append("TELEGRAM_BOT_TOKEN")
        if not self.llm_api_key:
            gaps.append("OPENROUTER_API_KEY")
        return gaps

    def user_allowed(self, user_id: int) -> bool:
        return not self.allowed_user_ids or user_id in self.allowed_user_ids


settings = Settings.load()
