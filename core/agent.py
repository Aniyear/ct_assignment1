"""Agent core: the model → tool → model loop.

This is where the decision-making of the system lives: which tool to call, with which
arguments, and when to stop. The depth of the loop is hard-limited.
"""

import json
import time
from typing import Any, Dict, List, Tuple

import requests

from config.settings import Settings
from core.tool_log import tool_log
from core.tools import TOOLS_SCHEMA, FinanceTools, today_for
from core.users import UserProfile

SYSTEM_PROMPT = """You are a personal finance assistant inside Telegram. Answer briefly and to the point.
Always reply in the same language the user writes in.

User context:
- Today: {today}
- Currency: {currency}
- Time zone: {timezone}

Rules:
1. Any change to data must go through a tool. Without a tool call nothing is saved.
2. Never say that something was saved if the tool returned ok=false. Say plainly that it failed and why.
3. Never invent amounts or balances. Use only numbers returned by tools.
4. If you do not know the exact account or category name, call list_accounts or list_categories first.
5. If the user did not name a category, pick the closest existing one instead of asking about small details.
6. Reply in plain text for Telegram: no markdown headings (#), no tables, no asterisks. Use emoji and bullet dots.
7. Write amounts with a thousands separator and the currency, for example 12 500 {currency}.
8. If asked for advice, first look at the real numbers with summary, then give the advice."""


class Agent:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ───── model call ─────

    def _chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = f"{self.settings.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "tools": TOOLS_SCHEMA,
            "tool_choice": "auto",
            "temperature": 0.3,
        }
        try:
            response = requests.post(url, headers=headers, json=payload,
                                     timeout=self.settings.llm_timeout, verify=False)
        except Exception as exc:
            return {"error": f"Model unavailable: {exc}"}
        if response.status_code >= 400:
            return {"error": f"Model returned {response.status_code}: {response.text[:300]}"}
        try:
            return response.json()
        except Exception:
            return {"error": "Model returned a non-JSON body"}

    def _system_message(self, profile: UserProfile) -> Dict[str, str]:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                today=today_for(profile).isoformat(),
                currency=profile.currency,
                timezone=profile.timezone,
            ),
        }

    # ───── main loop ─────

    def respond(self, profile: UserProfile, history: List[Dict[str, Any]],
                user_text: str) -> Tuple[str, List[str]]:
        """Returns (reply, list of tools that were called)."""
        tools = FinanceTools(profile)
        messages: List[Dict[str, Any]] = [self._system_message(profile)]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        used_tools: List[str] = []

        for _ in range(self.settings.max_tool_iterations):
            data = self._chat(messages)
            if data.get("error"):
                return f"⚠️ {data['error']}", used_tools

            choices = data.get("choices") or []
            if not choices:
                return "⚠️ The model returned an empty response.", used_tools

            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                return (message.get("content") or "I did not understand the request.").strip(), used_tools

            messages.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                function = call.get("function", {})
                name = function.get("name", "")
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except Exception:
                    arguments = {}

                started = time.time()
                result = tools.call(name, arguments)
                duration_ms = int((time.time() - started) * 1000)

                used_tools.append(name)
                tool_log.record(profile.user_id, name, arguments,
                                bool(result.get("ok")), duration_ms, result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return ("⚠️ Too many steps in a row, I stopped. "
                "Please rephrase the request more simply."), used_tools
