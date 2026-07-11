"""Canonical outbound URL safety for adapters.

Single source of truth for SSRF and privacy hazards on any URL the kit fetches,
renders, or sends to a provider. Extracted unchanged from the PageSpeed live
adapter so every adapter enforces one identical policy instead of competing
implementations.

Rejects: non-http(s) schemes, missing hosts, embedded credentials, non-standard
ports, credential-like query keys, and hosts resolving to any non-global address
(loopback, private, link-local including cloud metadata 169.254.169.254,
reserved, multicast, unspecified). Returns a canonicalized URL on success.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_TARGET_PORTS = frozenset({80, 443})
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "code",
        "id_token",
        "key",
        "password",
        "refresh_token",
        "secret",
        "session",
        "signature",
        "token",
    }
)


def validate_public_url(url: str) -> str:
    """Canonicalize a public target and reject common SSRF/privacy hazards."""
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
    if sorted(query_keys & SENSITIVE_QUERY_KEYS):
        raise ValueError("URL query contains credential-like fields and cannot be sent")

    lookup_port = port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, lookup_port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"URL host cannot be resolved: {host}") from exc
    addresses = {info[4][0] for info in infos}
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


def host_is_public(host: str) -> bool:
    """True when every resolved address for `host` is globally routable.

    Used as a defence-in-depth guard for browser subresource requests, where the
    browser (not urllib) performs the fetch.
    """
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True
