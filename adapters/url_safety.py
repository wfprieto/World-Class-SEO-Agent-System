"""Canonical outbound URL safety for adapters.

Single source of truth for SSRF and privacy hazards on any URL the kit fetches,
renders, or sends to a provider.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from collections.abc import Callable

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_TARGET_PORTS = frozenset({80, 443})
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token", "api_key", "apikey", "auth", "authorization",
        "client_secret", "code", "id_token", "key", "password",
        "refresh_token", "secret", "session", "signature", "token",
    }
)
Resolver = Callable[..., list[tuple]]
_EVIDENCE_HEADER_ALLOWLIST = frozenset(
    {"cache-control", "content-length", "content-type", "etag", "last-modified", "vary"}
)
_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_SECRET_IN_TEXT = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie|token|api[_-]?key|secret|password)"
    r"\s*[:=]\s*[^,;\s]+"
)
_BEARER_IN_TEXT = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")


def _address_is_public(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def validate_public_url(url: str, *, resolver: Resolver = socket.getaddrinfo) -> str:
    """Canonicalize a public target and reject common SSRF/privacy hazards.

    Literal IP hosts are validated before resolution. Hostnames are then resolved through
    an injectable resolver so tests remain hermetic without weakening production policy.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("URL contains an invalid host or port") from exc

    if scheme not in ALLOWED_SCHEMES or not host:
        raise ValueError("URL must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")
    if port is not None and port not in ALLOWED_TARGET_PORTS:
        raise ValueError("Only standard HTTP and HTTPS ports are allowed")

    query_keys = {
        key.lower()
        for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    if query_keys & SENSITIVE_QUERY_KEYS:
        raise ValueError("URL query contains credential-like fields and cannot be sent")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise ValueError(f"URL host resolves to a non-public address: {literal.compressed}")
    else:
        lookup_port = port or (443 if scheme == "https" else 80)
        try:
            infos = resolver(host, lookup_port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"URL host cannot be resolved: {host}") from exc
        addresses = {str(info[4][0]) for info in infos}
        if not addresses:
            raise ValueError("URL host resolved to no addresses")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise ValueError("URL host returned an invalid address") from exc
            if not ip.is_global:
                raise ValueError(f"URL host resolves to a non-public address: {ip.compressed}")

    if port == (443 if scheme == "https" else 80):
        port = None
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port is None else f"{display_host}:{port}"
    return urllib.parse.urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def host_is_public(host: str, *, resolver: Resolver = socket.getaddrinfo) -> bool:
    """Return true only when a literal or every resolved address is globally routable."""
    if not host:
        return False
    normalized = host.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(normalized)
    except ValueError:
        literal = None
    if literal is not None:
        return literal.is_global
    try:
        infos = resolver(normalized, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    return bool(infos) and all(_address_is_public(str(info[4][0])) for info in infos)


def sanitize_url_for_evidence(url: str) -> str:
    """Return a display-only URL with credentials, query, and fragment removed."""
    try:
        parsed = urllib.parse.urlsplit(str(url))
        host = parsed.hostname or ""
        port = parsed.port
    except (TypeError, ValueError):
        return "[REDACTED_URL]"
    if not parsed.scheme or not host:
        return "[REDACTED_URL]"
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port is None else f"{display_host}:{port}"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", "", ""))


def sanitize_headers_for_evidence(headers: dict) -> dict[str, str]:
    """Expose only non-secret response metadata headers."""
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() in _EVIDENCE_HEADER_ALLOWLIST
    }


def sanitize_text_for_evidence(value: object) -> str:
    """Redact credential-like text and strip URL queries from exported messages."""
    text = str(value)
    text = _URL_IN_TEXT.sub(lambda match: sanitize_url_for_evidence(match.group(0)), text)
    text = _BEARER_IN_TEXT.sub("Bearer [REDACTED]", text)
    text = _SECRET_IN_TEXT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text
