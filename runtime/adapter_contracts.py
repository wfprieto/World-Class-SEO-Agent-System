"""Compatibility imports for the canonical implementation-neutral adapter contracts."""

from __future__ import annotations

from contracts.adapter import (
    BLOCKING_ADAPTER_STATUSES,
    CANONICAL_ADAPTER_STATUSES,
    INVALID_ADAPTER_STATUSES,
    MISSING_ADAPTER_STATUSES,
    PARTIAL_ADAPTER_STATUSES,
    SUCCESS_ADAPTER_STATUSES,
    AdapterNotConfigured,
    AdapterResult,
    AdapterStatus,
    RuntimeAdapter,
    SEOAdapter,
    is_adapter_status,
    validate_adapter_result,
)

__all__ = [
    "BLOCKING_ADAPTER_STATUSES",
    "CANONICAL_ADAPTER_STATUSES",
    "INVALID_ADAPTER_STATUSES",
    "MISSING_ADAPTER_STATUSES",
    "PARTIAL_ADAPTER_STATUSES",
    "SUCCESS_ADAPTER_STATUSES",
    "AdapterNotConfigured",
    "AdapterResult",
    "AdapterStatus",
    "RuntimeAdapter",
    "SEOAdapter",
    "is_adapter_status",
    "validate_adapter_result",
]
