"""Tool call log.

Not cosmetic: without it we could not honestly answer the self-evaluation part of the
assignment, because the agent must be able to observe its own actions and their outcome.
"""

from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List

MAX_ENTRIES = 300
MAX_VALUE_CHARS = 300


def _short(value: Any) -> str:
    text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[:MAX_VALUE_CHARS] + "…"


class ToolLog:
    def __init__(self) -> None:
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=MAX_ENTRIES)

    def record(self, user_id: int, tool: str, args: Dict[str, Any], ok: bool,
               duration_ms: int, result: Any) -> None:
        self._entries.append({
            "time": datetime.now().strftime("%d.%m %H:%M:%S"),
            "user_id": user_id,
            "tool": tool,
            "args": _short(args),
            "ok": ok,
            "duration_ms": duration_ms,
            "result": _short(result),
        })

    def recent(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        items = [entry for entry in self._entries if entry["user_id"] == user_id]
        return items[-limit:]

    def stats(self, user_id: int) -> Dict[str, Any]:
        items = [entry for entry in self._entries if entry["user_id"] == user_id]
        if not items:
            return {"calls": 0, "errors": 0, "avg_ms": 0, "top": []}
        errors = sum(1 for entry in items if not entry["ok"])
        avg = sum(entry["duration_ms"] for entry in items) // len(items)
        counter: Dict[str, int] = {}
        for entry in items:
            counter[entry["tool"]] = counter.get(entry["tool"], 0) + 1
        top = sorted(counter.items(), key=lambda pair: pair[1], reverse=True)[:5]
        return {"calls": len(items), "errors": errors, "avg_ms": avg, "top": top}


tool_log = ToolLog()
