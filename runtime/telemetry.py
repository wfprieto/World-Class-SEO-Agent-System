"""Bounded runtime telemetry with recursive secret redaction."""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

_SENSITIVE = re.compile(r"(?i)(authorization|api[_-]?key|access[_-]?token|password|secret|cookie|session)")


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("[REDACTED]" if _SENSITIVE.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str) and re.search(r"(?:sk-(?:proj-)?|gh[pousr]_|AIza)[A-Za-z0-9_-]{12,}", value):
        return "[REDACTED]"
    return value


@dataclass
class OperationTelemetry:
    operation: str
    started_monotonic: float = field(default_factory=time.monotonic, repr=False)
    status: str = "STARTED"
    request_count: int = 0
    retry_count: int = 0
    units: int = 0
    estimated_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, *, status: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self.status = status
        if metadata:
            self.metadata.update(dict(metadata))
        payload = asdict(self)
        payload.pop("started_monotonic", None)
        payload["duration_ms"] = round((time.monotonic() - self.started_monotonic) * 1000, 3)
        payload["metadata"] = redact(payload["metadata"])
        return payload
