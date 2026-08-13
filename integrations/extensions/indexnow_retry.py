"""Small retry helper for bounded IndexNow submissions."""

from __future__ import annotations

import time
import urllib.error
from collections.abc import Callable
from typing import Any

MAX_RETRIES = 5
MAX_RESPONSE_BYTES = 65_536


def read_response(response: Any) -> tuple[int, bytes]:
    status_code = int(getattr(response, "status", response.getcode()))
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("IndexNow response exceeded the safe size limit")
    return status_code, raw


def retryable(exc: urllib.error.HTTPError) -> bool:
    return int(exc.code) in {429, 500, 502, 503, 504}


def post_with_retries(
    active: Callable[..., Any],
    request: Any,
    *,
    timeout: float,
    retries: int,
    retry_backoff_seconds: float,
) -> tuple[int, bytes, int]:
    if not 0 <= retries <= MAX_RETRIES:
        raise ValueError(f"retries must be between 0 and {MAX_RETRIES}")
    if retry_backoff_seconds < 0:
        raise ValueError("retry_backoff_seconds must be non-negative")
    attempts = 0
    while True:
        attempts += 1
        try:
            status_code, raw = read_response(active(request, timeout=timeout))
            return status_code, raw, attempts
        except urllib.error.HTTPError as exc:
            status_code = int(exc.code)
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            if attempts > retries or not retryable(exc):
                return status_code, raw, attempts
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds)
