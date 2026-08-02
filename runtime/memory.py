"""Redacted, bounded memory stores for SEO runtime sessions."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from sensitive_data import redact


def _session_key(session_id: str) -> str:
    """Return a stable non-reversible local lookup key for one session."""
    return "sha256:" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()


class MemoryStore(Protocol):
    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Store a redacted runtime event."""

    def load(self, session_id: str) -> list[dict[str, Any]]:
        """Load stored events for a session."""

    def delete_session(self, session_id: str) -> int:
        """Delete one session's events and return the number removed."""


class InMemoryStore:
    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._events.setdefault(_session_key(session_id), []).append(redact(event))

    def load(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(_session_key(session_id), []))

    def delete_session(self, session_id: str) -> int:
        with self._lock:
            key = _session_key(session_id)
            removed = len(self._events.get(key, []))
            self._events.pop(key, None)
            return removed


class JsonlMemoryStore:
    """Append-only local memory with redaction, locking, and session deletion."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with suppress(OSError):
            os.chmod(self.path.parent, 0o700)

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        payload = {"session_id": _session_key(session_id), "event": redact(event)}
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
            with suppress(OSError):
                os.chmod(self.path, 0o600)

    def load(self, session_id: str) -> list[dict[str, Any]]:
        key = _session_key(session_id)
        with self._lock:
            if not self.path.exists():
                return []
            events: list[dict[str, Any]] = []
            for line_number, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid memory record at line {line_number}") from exc
                if payload.get("session_id") == key:
                    event = payload.get("event", {})
                    if isinstance(event, dict):
                        events.append(event)
            return events

    def delete_session(self, session_id: str) -> int:
        key = _session_key(session_id)
        with self._lock:
            if not self.path.exists():
                return 0
            kept: list[str] = []
            removed = 0
            for line_number, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid memory record at line {line_number}") from exc
                if payload.get("session_id") == key:
                    removed += 1
                else:
                    kept.append(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(("\n".join(kept) + ("\n" if kept else "")), encoding="utf-8")
            temporary.replace(self.path)
            return removed
