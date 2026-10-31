"""Canonical evidence URL identity and deterministic JSON-pointer drift."""
from __future__ import annotations

import urllib.parse
from collections.abc import Iterator
from typing import Any

from sensitive_data import SENSITIVE_QUERY_KEYS


def canonicalize_url(url: str) -> str:
    """Return a stable URL identity without fragments or embedded credentials."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    parsed = urllib.parse.urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")

    query_keys = {
        key.lower()
        for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    sensitive = sorted(query_keys & SENSITIVE_QUERY_KEYS)
    if sensitive:
        raise ValueError(
            "URL query contains credential-like fields: " + ", ".join(sensitive)
        )

    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("url contains an invalid host or port") from exc

    if port == (80 if scheme == "http" else 443):
        port = None
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port is None else f"{display_host}:{port}"
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, ""))


def _json_pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _iter_drift(before: Any, after: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield JSON-Pointer-style differences while preserving missing vs null."""
    if isinstance(before, dict) and isinstance(after, dict):
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield child, {"change": "removed", "before": before[key]}
        for key in sorted(after_keys - before_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield child, {"change": "added", "after": after[key]}
        for key in sorted(before_keys & after_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield from _iter_drift(before[key], after[key], child)
        return

    # Treat arrays as ordered values. Reordering is material unless a metric
    # schema defines its own normalization before storage.
    if before != after:
        yield path or "/", {"change": "changed", "before": before, "after": after}
def compare_snapshots(
    recent: list[dict[str, Any]], url: str, metric_group: str,
    schema_version: str | None,
) -> dict[str, Any]:
    """Compare verified compatible snapshots without mutating persisted evidence."""
    if len(recent) < 2:
        return {
            "status": "insufficient_history",
            "url": canonicalize_url(url),
            "metric_group": metric_group,
            "schema_version": schema_version,
            "have": len(recent),
        }

    current, previous = recent[0], recent[1]
    if current["schema_version"] != previous["schema_version"]:
        return {
            "status": "schema_mismatch",
            "url": current["url"],
            "metric_group": metric_group,
            "current_schema": current["schema_version"],
            "previous_schema": previous["schema_version"],
            "current_id": current["id"],
            "previous_id": previous["id"],
        }

    drift = dict(_iter_drift(previous["payload"], current["payload"]))
    return {
        "status": "ok",
        "url": current["url"],
        "metric_group": metric_group,
        "schema_version": current["schema_version"],
        "from": previous["captured_at"],
        "to": current["captured_at"],
        "previous_id": previous["id"],
        "current_id": current["id"],
        "drift": drift,
        "drift_count": len(drift),
    }
