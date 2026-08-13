"""Bounded runtime telemetry with recursive secret redaction."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from sensitive_data import redact


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
        sanitized = redact(payload)
        if not isinstance(sanitized, dict):
            raise TypeError("telemetry redaction must preserve mapping shape")
        return sanitized
