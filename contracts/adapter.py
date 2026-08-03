"""Typed, validated contracts shared by runtime and concrete SEO adapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Generic, Literal, Protocol, TypeGuard, TypeVar, runtime_checkable


class AdapterNotConfigured(RuntimeError):
    """Raised when credentials or source files are missing."""


AdapterDataT = TypeVar("AdapterDataT")
AdapterStatus = Literal[
    "ok",
    "complete",
    "success",
    "needs-review",
    "partial",
    "empty",
    "not_found",
    "not_configured",
    "invalid",
    "invalid_response",
    "blocked",
    "failed",
    "unauthorized",
    "rate_limited",
]
CANONICAL_ADAPTER_STATUSES: frozenset[str] = frozenset(
    {
        "ok",
        "complete",
        "success",
        "needs-review",
        "partial",
        "empty",
        "not_found",
        "not_configured",
        "invalid",
        "invalid_response",
        "blocked",
        "failed",
        "unauthorized",
        "rate_limited",
    }
)
SUCCESS_ADAPTER_STATUSES: frozenset[str] = frozenset({"ok", "complete", "success"})
PARTIAL_ADAPTER_STATUSES: frozenset[str] = frozenset({"needs-review", "partial"})
MISSING_ADAPTER_STATUSES: frozenset[str] = frozenset(
    {"empty", "not_found", "not_configured"}
)
INVALID_ADAPTER_STATUSES: frozenset[str] = frozenset({"invalid", "invalid_response"})
BLOCKING_ADAPTER_STATUSES: frozenset[str] = frozenset(
    {"blocked", "failed", "unauthorized", "rate_limited"}
)
_SECRET_PATTERN = re.compile(
    r"(?i)(?:authorization\s*:\s*bearer\s+\S+|(?:api[_-]?key|token|secret|password)\s*[=:]\s*\S+)"
)


@dataclass
class AdapterResult(Generic[AdapterDataT]):
    """Untrusted adapter response; validate it before runtime consumption."""

    source: str
    status: str
    data: AdapterDataT
    warnings: list[str]


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Single adapter protocol used by registry, integrations, and dispatcher."""

    def fetch(self, **kwargs: Any) -> AdapterResult[Any]:
        """Fetch or parse data and return a normalized adapter result."""


SEOAdapter = RuntimeAdapter


def is_adapter_status(value: object) -> TypeGuard[AdapterStatus]:
    """Return whether an untrusted value is a canonical adapter status."""

    return isinstance(value, str) and value in CANONICAL_ADAPTER_STATUSES


def validate_adapter_result(result: object) -> AdapterResult[Any]:
    """Reject malformed, unsafe, or non-serializable adapter boundary values."""

    if not isinstance(result, AdapterResult):
        raise TypeError("adapter fetch() must return AdapterResult")
    if not isinstance(result.source, str) or not result.source.strip():
        raise TypeError("adapter result source must be a non-empty string")
    if not isinstance(result.status, str) or not result.status.strip():
        raise TypeError("adapter result status must be a non-empty string")
    if not is_adapter_status(result.status):
        raise ValueError(f"unsupported adapter result status: {result.status!r}")
    if not isinstance(result.warnings, list) or any(
        not isinstance(item, str) for item in result.warnings
    ):
        raise TypeError("adapter result warnings must be a list of strings")
    if any(_SECRET_PATTERN.search(item) for item in result.warnings):
        raise ValueError("adapter result warnings must not contain credential material")
    try:
        json.dumps(result.data, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError("adapter result data must be finite JSON-serializable data") from exc
    return result
