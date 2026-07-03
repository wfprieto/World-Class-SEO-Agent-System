"""Memory stores for SEO runtime sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class MemoryStore(Protocol):
    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Store a runtime event."""

    def load(self, session_id: str) -> list[dict[str, Any]]:
        """Load stored events for a session."""


class InMemoryStore:
    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = {}

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        self._events.setdefault(session_id, []).append(event)

    def load(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._events.get(session_id, []))


class JsonlMemoryStore:
    """Append-only local memory for agent runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        payload = {"session_id": session_id, "event": event}
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, sort_keys=True) + "\n")

    def load(self, session_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            if payload.get("session_id") == session_id:
                events.append(payload.get("event", {}))
        return events
