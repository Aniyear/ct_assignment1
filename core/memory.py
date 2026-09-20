"""Short-term conversation memory.

The honest name matters for the report: this is a sliding window of the latest turns
kept in RAM, not long-term memory. The long-term memory of the system is the Notion
databases plus the persisted user profiles.
"""

from collections import defaultdict, deque
from typing import Any, Deque, Dict, List

MAX_TURNS = 12


class ConversationMemory:
    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self._max_turns = max_turns
        self._store: Dict[int, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self._max_turns)
        )

    def history(self, user_id: int) -> List[Dict[str, Any]]:
        return list(self._store[user_id])

    def add(self, user_id: int, role: str, content: str) -> None:
        self._store[user_id].append({"role": role, "content": content})

    def clear(self, user_id: int) -> None:
        self._store[user_id].clear()

    def size(self, user_id: int) -> int:
        return len(self._store[user_id])
