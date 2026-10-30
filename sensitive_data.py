"""Canonical bounded secret redaction for persistence, memory, and telemetry."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote_plus

REDACTED = "[REDACTED]"
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "code",
        "credential",
        "id_token",
        "key",
        "password",
        "passwd",
        "refresh_token",
        "secret",
        "session",
        "sessionid",
        "signature",
        "token",
    }
)

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
    r"(?i)(\b(?:authorization|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|"
    r"password|passwd|secret|private[_ -]?key|cookie|set-cookie|session(?:[_ -]?id)?|credential|"
    r"token|auth|signature|"
    r'''client[_ -]?(?:secret|id))["']?\s*[:=]\s*)("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s,;&]+)'''
)
_AUTH_SCHEME_SECRET = re.compile(r"(?i)(\b(?:authorization\s*:\s*)?(?:bearer|basic)\s+)([^\s,;]+)")
_HTML_ENTITY = r"&(?:\#[0-9]+|\#x[0-9a-f]+|[a-z]+);"
_QUERY_FIELD = re.compile(
    r"([?&](?:amp;|\#0*38;|\#x0*26;)?)"
    rf'''((?:[^=&#\s"'<>]|{_HTML_ENTITY})+)=([^&#\s"'<>]*)''',
    re.IGNORECASE,
)
_URL_USERINFO = re.compile(
    rf'''(https?://)(?:[^/\s?#<>"'&]|{_HTML_ENTITY})*(?:@|&(?:commat|\#0*64|\#x0*40);)''',
    re.IGNORECASE,
)
_NORMALIZED_QUERY_KEYS = frozenset(re.sub(r"[^a-z0-9]", "", key) for key in SENSITIVE_QUERY_KEYS)


def sensitive_query_key(key: str) -> bool:
    """Recognize canonical aliases after bounded HTML/percent name decoding."""
    for _ in range(3):
        decoded = unquote_plus(html.unescape(key))
        if decoded == key:
            break
        key = decoded
    return re.sub(r"[^a-z0-9]", "", key.casefold()) in _NORMALIZED_QUERY_KEYS


def query_contains_credentials(query: str) -> bool:
    """Offline privacy check; it neither changes the approved URL nor resolves DNS."""
    return any(sensitive_query_key(field.partition("=")[0])
               for field in html.unescape(query).split("&"))


def _redact_query_field(match: re.Match[str]) -> str:
    prefix, name, value = match.groups()
    return f"{prefix}{name}={REDACTED if sensitive_query_key(name) else value}"


def _redact_labeled_secret(match: re.Match[str]) -> str:
    prefix, value = match.groups()
    quote = value[0] if value.startswith(('"', "'")) and value[-1:] == value[0] else ""
    return f"{prefix}{quote}{REDACTED}{quote}"


def redact_mapping_keys(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project string keys too, retaining all entries when redacted identities collide."""
    result: dict[str, Any] = {}
    next_ordinal: dict[str, int] = {}
    projected = [(key, str(redact(key)), item) for key, item in value.items()]
    reserved = {key for key, safe_key, _ in projected if key == safe_key}
    for key, safe_key, item in projected:
        candidate = safe_key
        ordinal = next_ordinal.get(safe_key, 2)
        while candidate in result or (key != safe_key and candidate in reserved):
            candidate = f"{safe_key} [redacted-key-{ordinal}]"
            ordinal += 1
        result[candidate] = item
        next_ordinal[safe_key] = ordinal
    return result


def redact(value: Any, *, key: str = "") -> Any:
    """Recursively redact bounded credential forms without logging the input."""
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, Mapping):
        return redact_mapping_keys({str(item_key): redact(item, key=str(item_key))
                                    for item_key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    result = _URL_USERINFO.sub(r"\1", value)
    result = _QUERY_FIELD.sub(_redact_query_field, result)
    result = _AUTH_SCHEME_SECRET.sub(r"\1[REDACTED]", result)
    result = _LABELED_SECRET.sub(_redact_labeled_secret, result)
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
