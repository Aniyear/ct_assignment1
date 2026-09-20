"""Service-level settings.

Only service-wide values live here: bot token, model provider, port.
Per-user data (their Notion token and their database IDs) is DELIBERATELY not here:
it lives in core/users.py. That separation is what makes the bot multi-tenant.

Provider switching
------------------
The agent talks to any OpenAI-compatible chat-completions endpoint, so the provider is
just configuration. Set AI_PROVIDER and the matching API key:

    AI_PROVIDER=gemini      + GEMINI_API_KEY        (Google AI Studio)
    AI_PROVIDER=openrouter  + OPENROUTER_API_KEY    (default)
    AI_PROVIDER=groq        + GROQ_API_KEY
    AI_PROVIDER=custom      + LLM_API_KEY + LLM_BASE_URL + LLM_MODEL

LLM_BASE_URL and LLM_MODEL always win over the preset if they are set explicitly.
The chosen model MUST support function calling, otherwise the agent cannot write to Notion.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # in production the variables may already be in the environment
    pass


# provider -> (base url, default model, env variable holding the key)
PROVIDERS: Dict[str, Dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-chat",
        "key_env": "OPENROUTER_API_KEY",
        "label": "OpenRouter",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
        "label": "Google Gemini",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
        "label": "Groq",
    },
    "custom": {
        "base_url": "",
        "model": "",
        "key_env": "LLM_API_KEY",
        "label": "Custom OpenAI-compatible endpoint",
    },
}

# "google" and "googleai" are accepted as aliases of "gemini"
PROVIDER_ALIASES = {"google": "gemini", "googleai": "gemini", "google_ai": "gemini"}


def _parse_ids(raw: str) -> List[int]:
    result: List[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return result


def _resolve_provider() -> str:
    raw = os.getenv("AI_PROVIDER", "").strip().lower()
    raw = PROVIDER_ALIASES.get(raw, raw)
    if raw in PROVIDERS:
        return raw
    if raw:
        print(f"[settings] Unknown AI_PROVIDER='{raw}', falling back to openrouter")
    return "openrouter"


def _resolve_key(provider: str) -> str:
    """Takes the key of the selected provider, with sensible fallbacks.

    Checked in order: the provider's own variable, the generic LLM_API_KEY, and finally
    OPENROUTER_API_KEY so that older .env files keep working.
    """
    candidates = [PROVIDERS[provider]["key_env"], "LLM_API_KEY", "OPENROUTER_API_KEY"]
    for name in candidates:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


@dataclass
class Settings:
    telegram_bot_token: str = ""
    provider: str = "openrouter"
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
        provider = _resolve_provider()
        preset = PROVIDERS[provider]

        # An explicit LLM_BASE_URL / LLM_MODEL always overrides the preset.
        base_url = os.getenv("LLM_BASE_URL", "").strip() or preset["base_url"]
        model = (
            os.getenv("LLM_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "").strip()
            or preset["model"]
        )

        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            provider=provider,
            llm_api_key=_resolve_key(provider),
            llm_model=model,
            llm_base_url=base_url.rstrip("/"),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            max_tool_iterations=int(os.getenv("MAX_TOOL_ITERATIONS", "6")),
            users_file=os.getenv("USERS_FILE", "data/users.json"),
            allowed_user_ids=_parse_ids(os.getenv("ALLOWED_USER_IDS", "")),
            default_currency=os.getenv("DEFAULT_CURRENCY", "KZT"),
            timezone=os.getenv("TIMEZONE", "Asia/Almaty"),
            port=int(os.getenv("PORT", "8080")),
        )

    @property
    def provider_label(self) -> str:
        return PROVIDERS.get(self.provider, {}).get("label", self.provider)

    def missing(self) -> List[str]:
        """What is missing for a successful start. Better to say it now than crash later."""
        gaps = []
        if not self.telegram_bot_token:
            gaps.append("TELEGRAM_BOT_TOKEN")
        if not self.llm_api_key:
            gaps.append(PROVIDERS[self.provider]["key_env"])
        if not self.llm_base_url:
            gaps.append("LLM_BASE_URL")
        if not self.llm_model:
            gaps.append("LLM_MODEL")
        return gaps

    def user_allowed(self, user_id: int) -> bool:
        return not self.allowed_user_ids or user_id in self.allowed_user_ids


settings = Settings.load()
