"""Compatibility imports for the canonical implementation-neutral adapter contracts."""

from __future__ import annotations

from contracts.adapter import (
    AdapterNotConfigured,
    AdapterResult,
    RuntimeAdapter,
    SEOAdapter,
    validate_adapter_result,
)

__all__ = [
    "AdapterNotConfigured",
    "AdapterResult",
    "RuntimeAdapter",
    "SEOAdapter",
    "validate_adapter_result",
]

