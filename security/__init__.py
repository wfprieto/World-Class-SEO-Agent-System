"""Fail-closed security policies shared by executable layers."""

from security.url_safety import (
    ALLOWED_SCHEMES,
    ALLOWED_TARGET_PORTS,
    Resolver,
    host_is_public,
    sanitize_headers_for_evidence,
    sanitize_text_for_evidence,
    sanitize_url_for_evidence,
    validate_public_url,
)

__all__ = [
    "ALLOWED_SCHEMES",
    "ALLOWED_TARGET_PORTS",
    "Resolver",
    "host_is_public",
    "sanitize_headers_for_evidence",
    "sanitize_text_for_evidence",
    "sanitize_url_for_evidence",
    "validate_public_url",
]
