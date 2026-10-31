"""Concrete inert target and grant grammar; never performs DNS or provider calls."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
from urllib.parse import SplitResult, urlsplit, urlunsplit

from integrations.extensions.indexnow import MAX_URLS
from scripts import publication_policy as policy
from scripts.publication_subject import JsonObject, exact_keys, object_value, string_value
from security.url_safety import ALLOWED_TARGET_PORTS
from sensitive_data import query_contains_credentials


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _public_ip(text: str) -> str | None:
    if "%" in text:
        raise ValueError("Scoped IP zones are not canonical outbound targets")
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if not address.is_global or address.is_multicast or address.is_unspecified:
        raise ValueError("Publication targets cannot name a nonpublic IP address")
    return str(address)


def normalize_host(value: object, *, allow_ip: bool = False) -> str:
    text = unicodedata.normalize("NFC", string_value(value, "target host")).lower().rstrip(".")
    address = _public_ip(text)
    if address is not None:
        if not allow_ip:
            raise ValueError("This target requires a domain, not a literal IP")
        return address
    try:
        encoded = text.encode("idna").decode("ascii")
        decoded = encoded.encode("ascii").decode("idna")
    except UnicodeError:
        raise ValueError("Target host is not an unambiguous IDNA domain") from None
    if any(ord(character) > 127 for character in text) and decoded != text:
        raise ValueError("Lossy or ambiguous international host mapping is forbidden")
    labels = encoded.split(".")
    if (len(encoded) > 253 or len(labels) < 2 or re.search(r"[a-z]", labels[-1]) is None
            or any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None for label in labels)
            or labels[-1] in {"local", "localhost", "internal", "invalid", "test", "example", "onion"}):
        raise ValueError("Target must be a concrete public domain, never a wildcard or local name")
    return encoded


def _url_authority(text: str) -> tuple[SplitResult, str, int | None]:
    try:
        parts = urlsplit(text)
        if parts.scheme.lower() not in {"http", "https"} or parts.username is not None or parts.password is not None:
            raise ValueError("Target URL must be HTTP(S) without user information")
        if query_contains_credentials(parts.query):
            raise ValueError("Credential-bearing target URLs cannot enter public evidence")
        host = normalize_host(parts.hostname, allow_ip=True)
        port = parts.port
        if port is not None and port not in ALLOWED_TARGET_PORTS:
            raise ValueError("Target port is forbidden by canonical outbound policy")
    except (ValueError, TypeError):
        raise ValueError("Target URL authority is invalid") from None
    return parts, host, port


def canonical_url(value: object) -> str:
    text = string_value(value, "target URL")
    if (len(text) > 4096 or any(character.isspace() or unicodedata.category(character) == "Cc" for character in text)
            or "\\" in text or "#" in text):
        raise ValueError("Target URL contains a fragment, control or ambiguous separator")
    parts, host, port = _url_authority(text)
    path = parts.path or "/"
    if (any(segment in {".", ".."} for segment in path.split("/"))
            or re.search(r"%(?:2e|2f|5c|25)", path, re.IGNORECASE)
            or re.search(r"%(?![0-9a-fA-F]{2})", path)):
        raise ValueError("Ambiguous escaped or literal target path traversal is forbidden")
    scheme = parts.scheme.lower()
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != {"http": 80, "https": 443}[scheme]:
        authority += f":{port}"
    return urlunsplit((scheme, authority, path, parts.query, ""))


def _url_set(value: object) -> list[str]:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_URLS:
        raise ValueError("IndexNow requires a bounded nonempty URL set")
    urls = sorted({canonical_url(item) for item in value})
    if len({urlsplit(url).hostname for url in urls}) != 1:
        raise ValueError("IndexNow URL set must belong to exactly one authorized host")
    return urls


def normalize_target(value: object) -> JsonObject:
    data = object_value(value, "target descriptor")
    kind = string_value(data.get("kind"), "target kind")
    exact_keys(data, {"kind", "values" if kind == "indexnow_url_set" else "value"}, "target")
    if kind == "indexnow_url_set":
        return {"kind": kind, "values": _url_set(data["values"])}
    text = data["value"]
    if kind == "youtube_query":
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 500:
            raise ValueError("YouTube query must be a bounded actual query")
        result = unicodedata.normalize("NFC", text.strip())
    elif kind == "web_url":
        result = canonical_url(text)
    elif kind == "domain":
        result = normalize_host(text)
    elif kind == "gsc_property":
        source = string_value(text, "GSC property")
        result = "sc-domain:" + normalize_host(source[10:]) if source.startswith("sc-domain:") else canonical_url(source)
    elif kind == "ga4_property":
        source = string_value(text, "GA4 property").removeprefix("properties/")
        if re.fullmatch(r"[0-9]+", source) is None:
            raise ValueError("GA4 property must be its exact numeric resource identity")
        result = "properties/" + source
    else:
        raise ValueError("Unknown target descriptor kind")
    return {"kind": kind, "value": result}


def target_digest(value: object) -> str:
    return hashlib.sha256(canonical(normalize_target(value))).hexdigest()


def _targets(value: object, *, required: bool) -> list[JsonObject]:
    if not isinstance(value, list) or len(value) > policy.MAX_RECORDS or (required and not value):
        raise ValueError("Scope targets must be a bounded explicit list")
    normalized = [normalize_target(item) for item in value]
    serialized = [canonical(item) for item in normalized]
    if len(set(serialized)) != len(serialized):
        raise ValueError("Scope contains duplicate equivalent targets")
    return [row for _, row in sorted(zip(serialized, normalized, strict=True), key=lambda pair: pair[0])]


def _scope_strings(value: object, *, hosts: bool) -> list[str]:
    if not isinstance(value, list) or not 0 < len(value) <= policy.MAX_RECORDS:
        raise ValueError("Scope methods/hosts require bounded nonempty explicit lists")
    values = [normalize_host(item, allow_ip=True) if hosts else string_value(item, "scope method") for item in value]
    if len(set(values)) != len(values) or (not hosts and not set(values).issubset({"GET", "POST"})):
        raise ValueError("Scope has duplicate hosts/methods or unsupported request methods")
    return sorted(values)


def normalize_scope(value: object) -> JsonObject:
    scope = object_value(value, "authorized scope")
    exact_keys(scope, {"targets", "endpoint_hosts", "methods", "redirect_targets"}, "authorized scope")
    return {"targets": _targets(scope["targets"], required=True),
            "redirect_targets": _targets(scope["redirect_targets"], required=False),
            "endpoint_hosts": _scope_strings(scope["endpoint_hosts"], hosts=True),
            "methods": _scope_strings(scope["methods"], hosts=False)}


def scope_digest(value: object) -> str:
    return hashlib.sha256(canonical(normalize_scope(value))).hexdigest()
