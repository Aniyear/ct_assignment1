"""Ядро агента: цикл «модель → инструмент → модель».

Это то самое место, где живёт «принятие решения» системы: какой инструмент вызвать,
с какими аргументами и когда остановиться. Глубина цикла ограничена жёстко.
"""

import json
import time
from typing import Any, Dict, List, Tuple

import requests

from config.settings import Settings
from core.tool_log import tool_log
from core.tools import TOOLS_SCHEMA, FinanceTools, today_for
from core.users import UserProfile

SYSTEM_PROMPT = """Ты — личный финансовый ассистент в Telegram. Общаешься по-русски, коротко и по делу.

Данные пользователя:
- Сегодня: {today}
- Валюта: {currency}
- Часовой пояс: {timezone}

Правила работы:
1. Любое действие с данными делай только через инструменты. Без вызова инструмента ничего не сохранено.
2. Запрещено говорить «записал», если инструмент вернул ok=false. В этом случае скажи прямо, что не получилось, и почему.
3. Не выдумывай суммы и балансы. Цифры бери только из ответов инструментов.
4. Если не знаешь точного названия счёта или категории — сначала вызови list_accounts или list_categories.
5. Если пользователь не назвал категорию — подбери ближайшую по смыслу из существующих, не переспрашивай по мелочам.
6. Формат ответа — простой текст для Telegram: без markdown-заголовков (#), без таблиц, без звёздочек. Используй эмодзи и точки «•».
7. Суммы пиши с разделителем тысяч и валютой, например 12 500 {currency}.
8. Если просят совет — сначала посмотри реальные цифры через summary, потом давай совет."""


class Agent:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ───── вызов модели ─────

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
                                     timeout=self.settings.llm_timeout)
        except Exception as exc:
            return {"error": f"Модель недоступна: {exc}"}
        if response.status_code >= 400:
            return {"error": f"Модель вернула {response.status_code}: {response.text[:300]}"}
        try:
            return response.json()
        except Exception:
            return {"error": "Модель вернула не JSON"}

    def _system_message(self, profile: UserProfile) -> Dict[str, str]:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                today=today_for(profile).isoformat(),
                currency=profile.currency,
                timezone=profile.timezone,
            ),
        }

    # ───── основной цикл ─────

    def respond(self, profile: UserProfile, history: List[Dict[str, Any]],
                user_text: str) -> Tuple[str, List[str]]:
        """Возвращает (ответ, список вызванных инструментов)."""
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
                return "⚠️ Модель вернула пустой ответ.", used_tools

            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                return (message.get("content") or "Не понял запрос.").strip(), used_tools

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

        return ("⚠️ Слишком много шагов подряд, остановился. "
                "Сформулируй запрос короче."), used_tools
