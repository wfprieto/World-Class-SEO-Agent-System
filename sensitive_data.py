"""Canonical bounded secret redaction for persistence, memory, and telemetry."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|secret|private[_-]?key|cookie|session|credential|token|"
    r"client[_-]?(?:id|secret)|consent[_-]?string|tc[_-]?string|gclid)"
)
_TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
)
_LABELED_SECRET = re.compile(
    r"(?i)(\b(?:authorization|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
    r"password|passwd|secret|private[_ -]?key|cookie|set-cookie|session|credential|"
    r"token|auth|signature|"
    r"client[_ -]?secret)\s*[:=]\s*)([^\s,;&]+)"
)
_AUTH_SCHEME_SECRET = re.compile(
    r"(?i)(\b(?:authorization\s*:\s*)?(?:bearer|basic)\s+)([^\s,;]+)"
)
_SENSITIVE_QUERY = re.compile(
    r"(?i)([?&](?:access_token|api_key|apikey|auth|authorization|client_secret|"
    r"password|refresh_token|secret|session|signature|token)=)([^&#\s]*)"
)


def redact(value: Any, *, key: str = "") -> Any:
    """Recursively redact bounded credential forms without logging the input."""
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    result = _SENSITIVE_QUERY.sub(r"\1[REDACTED]", value)
    result = _AUTH_SCHEME_SECRET.sub(r"\1[REDACTED]", result)
    result = _LABELED_SECRET.sub(r"\1[REDACTED]", result)
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def redact_evidence_fields(
    source: str | None,
    run_id: str | None,
    payload: Mapping[str, Any],
    scope: Mapping[str, Any],
) -> tuple[str | None, str | None, dict[str, Any], dict[str, Any]]:
    """Redact an evidence record while preserving its required mapping shapes."""
    safe_payload = redact(payload)
    safe_scope = redact(scope)
    if not isinstance(safe_payload, dict) or not isinstance(safe_scope, dict):
        raise TypeError("sanitized evidence payload and scope must remain mappings")
    safe_source = None if source is None else str(redact(source))
    safe_run_id = None if run_id is None else str(redact(run_id))
    return safe_source, safe_run_id, safe_payload, safe_scope
