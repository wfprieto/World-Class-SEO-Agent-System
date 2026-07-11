"""Redacted, bounded memory stores for SEO runtime sessions."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Protocol


_SENSITIVE_KEYS = {
    "api_key", "apikey", "access_token", "refresh_token", "token", "secret",
    "password", "passwd", "authorization", "cookie", "set-cookie", "client_secret",
    "tc_string", "consent_string", "user_id", "client_id", "gclid",
}
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
)


def redact(value: Any, *, key: str = "") -> Any:
    """Recursively remove secrets and identifiers before memory persistence."""
    normalized_key = key.lower().replace("-", "_")
    if normalized_key in _SENSITIVE_KEYS or any(
        marker in normalized_key for marker in ("password", "secret", "private_key")
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result
    return value


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
            self._events.setdefault(session_id, []).append(redact(event))

    def load(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(session_id, []))

    def delete_session(self, session_id: str) -> int:
        with self._lock:
            removed = len(self._events.get(session_id, []))
            self._events.pop(session_id, None)
            return removed


class JsonlMemoryStore:
    """Append-only local memory with redaction, locking, and session deletion."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        payload = {"session_id": session_id, "event": redact(event)}
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def load(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            events: list[dict[str, Any]] = []
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid memory record at line {line_number}") from exc
                if payload.get("session_id") == session_id:
                    event = payload.get("event", {})
                    if isinstance(event, dict):
                        events.append(event)
            return events

    def delete_session(self, session_id: str) -> int:
        with self._lock:
            if not self.path.exists():
                return 0
            kept: list[str] = []
            removed = 0
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid memory record at line {line_number}") from exc
                if payload.get("session_id") == session_id:
                    removed += 1
                else:
                    kept.append(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(("\n".join(kept) + ("\n" if kept else "")), encoding="utf-8")
            temporary.replace(self.path)
            return removed
