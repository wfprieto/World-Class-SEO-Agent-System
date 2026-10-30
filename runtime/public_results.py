"""Public result projection, with explicit provenance for structural session state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sensitive_data import REDACTED, redact, redact_mapping_keys


class PublicSession(dict[str, Any]):
    """A projected SessionState mapping, not an exemption for untrusted named fields."""


def _public_field(key: str, value: Any) -> Any:
    if isinstance(value, PublicSession):
        return public_result(value)
    if key == "credential_transport" and value == "X-Goog-Api-Key header":
        return value
    if redact(None, key=key) == REDACTED:
        return REDACTED
    return public_result(value)


def public_result(value: Any) -> Any:
    """Copy public content through canonical redaction without mutating execution state."""
    if isinstance(value, PublicSession):
        return PublicSession({key: public_result(item) if key == "session_id"
                              else _public_field(key, item) for key, item in value.items()})
    if isinstance(value, Mapping):
        return redact_mapping_keys({str(key): _public_field(str(key), item)
                                    for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return [public_result(item) for item in value]
    return redact(value)


def public_result_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Typed mapping entry point for CLI and workflow export boundaries."""
    result = public_result(value)
    if not isinstance(result, dict):
        raise TypeError("public result projection must preserve a mapping")
    return result


def public_session_mapping(value: Mapping[str, Any]) -> PublicSession:
    """Project state from SessionState.to_dict while preserving its structural ID."""
    return PublicSession(public_result_mapping(PublicSession(value)))
