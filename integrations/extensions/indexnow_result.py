"""IndexNow response normalization."""

from __future__ import annotations

import urllib.parse

from contracts.adapter import AdapterResult
from integrations.extensions.indexnow_retry import MAX_RESPONSE_BYTES

STATE_BY_STATUS = {
    200: ("ok", "AVAILABLE"),
    202: ("partial", "PARTIAL"),
    400: ("invalid_response", "INVALID_RESPONSE"),
    403: ("unauthorized", "UNAUTHORIZED"),
    422: ("invalid_response", "INVALID_RESPONSE"),
    429: ("rate_limited", "RATE_LIMITED"),
}


def response_result(
    *,
    status_code: int,
    raw: bytes,
    secret: str,
    host: str,
    url_count: int,
    attempts: int,
    endpoint: str,
    key_location: str | None,
) -> AdapterResult:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("IndexNow response exceeded the safe size limit")
    state = STATE_BY_STATUS.get(status_code, ("failed", "FAILED"))
    return AdapterResult(
        source="indexnow",
        status=state[0],
        data={
            "state": state[1],
            "http_status": status_code,
            "host": host,
            "url_count": url_count,
            "attempts": attempts,
            "endpoint_host": urllib.parse.urlsplit(endpoint).hostname,
            "key_location": key_location,
            "response_excerpt": raw.decode("utf-8", errors="replace").replace(secret, "[REDACTED]")[:500],
        },
        warnings=[
            "HTTP 200/202 confirms receipt or pending key validation only; it does not prove crawling or indexing."
        ],
    )
