"""Bounded Google API transport with scoped OAuth and sanitized failures.

This module supports Google-owned JSON APIs only. It is not a generic URL
fetcher and therefore does not replace ``adapters/url_safety.py``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from http.client import HTTPResponse
from typing import Any, NoReturn

from contracts.google import _TRUTH_STATES as _TRUTH_STATES
from contracts.google import GoogleAPIError as GoogleAPIError
from contracts.google import _state_for_status as _state_for_status
from integrations.google.oauth import GoogleOAuthConfig as GoogleOAuthConfig
from integrations.google.oauth import GoogleOAuthProvider as GoogleOAuthProvider
from integrations.google.transport import _NoCrossHostRedirects as _NoCrossHostRedirects


class GoogleJsonClient:
    """GET or POST bounded JSON requests to explicitly approved Google hosts."""

    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        timeout: float = 60,
        max_retries: int = 2,
        max_response_bytes: int = 12_000_000,
        opener: urllib.request.OpenerDirector | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not allowed_hosts:
            raise ValueError("allowed_hosts cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not isinstance(max_retries, int) or not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be an integer from 0 to 5")
        if not isinstance(max_response_bytes, int) or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.allowed_hosts = set(allowed_hosts)
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self.max_response_bytes = int(max_response_bytes)
        self.opener = opener or urllib.request.build_opener(
            _NoCrossHostRedirects(self.allowed_hosts)
        )
        self.sleep = sleep
        self.last_telemetry: dict[str, Any] = {}

    def _prepare_request(
        self, endpoint: str, service: str, method: str, payload: dict[str, Any] | None,
        access_token: str | None, api_key: str | None,
        query: dict[str, str | int | None] | None,
    ) -> urllib.request.Request:
        parsed = urllib.parse.urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username
            or parsed.password
        ):
            raise GoogleAPIError(
                service,
                None,
                "endpoint is not an approved HTTPS Google API host",
                state="BLOCKED",
            )
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            raise ValueError("method must be GET or POST")
        params = {
            key: value
            for key, value in (query or {}).items()
            if value is not None
        }
        request_url = endpoint
        if params:
            request_url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if api_key:
            headers["X-Goog-Api-Key"] = api_key
        body = (
            json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if payload is not None
            else None
        )
        return urllib.request.Request(
            request_url,
            data=body,
            headers=headers,
            method=normalized_method,
        )

    def _read_response(self, response: HTTPResponse, service: str) -> dict[str, Any]:
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                if int(declared) > self.max_response_bytes:
                    raise GoogleAPIError(
                        service,
                        getattr(response, "status", None),
                        "response exceeds size limit",
                        state="INVALID_RESPONSE",
                    )
            except ValueError as exc:
                raise GoogleAPIError(
                    service,
                    getattr(response, "status", None),
                    "invalid Content-Length header",
                    state="INVALID_RESPONSE",
                ) from exc
        raw = response.read(self.max_response_bytes + 1)
        if len(raw) > self.max_response_bytes:
            raise GoogleAPIError(
                service,
                getattr(response, "status", None),
                "response exceeds size limit",
                state="INVALID_RESPONSE",
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GoogleAPIError(
                service,
                getattr(response, "status", None),
                "invalid JSON response",
                state="INVALID_RESPONSE",
            ) from exc
        if not isinstance(decoded, dict):
            raise GoogleAPIError(
                service,
                getattr(response, "status", None),
                "JSON response is not an object",
                state="INVALID_RESPONSE",
            )
        return decoded

    def _retry_http_error(
        self, exc: urllib.error.HTTPError, service: str, attempt: int,
        api_key: str | None, access_token: str | None,
    ) -> bool:
        self.last_telemetry["response_status"] = exc.code
        self.last_telemetry["rate_limited"] = exc.code == 429
        try:
            if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                delay = self._retry_delay(exc.headers.get("Retry-After"), attempt)
            else:
                self._raise_provider_error(exc, service, api_key, access_token)
        finally:
            exc.close()
        self.sleep(delay)
        return True

    def _raise_provider_error(
        self, exc: urllib.error.HTTPError, service: str,
        api_key: str | None, access_token: str | None,
    ) -> NoReturn:
        message = self._safe_error_message(exc)
        for secret in (api_key, access_token):
            if secret:
                message = message.replace(secret, "[REDACTED]")
                message = message.replace(
                    urllib.parse.quote(secret, safe=""),
                    "[REDACTED]",
                )
        raise GoogleAPIError(
            service,
            exc.code,
            message,
            state=_state_for_status(exc.code),
        ) from exc

    def request(
        self,
        endpoint: str,
        *,
        service: str,
        method: str = "POST",
        payload: dict[str, Any] | None = None,
        access_token: str | None = None,
        api_key: str | None = None,
        query: dict[str, str | int | None] | None = None,
    ) -> dict[str, Any]:
        request = self._prepare_request(endpoint, service, method, payload, access_token, api_key, query)
        self.last_telemetry = {
            "service": service,
            "request_attempts": 0,
            "retry_count": 0,
            "response_status": None,
            "rate_limited": False,
        }
        for attempt in range(self.max_retries + 1):
            self.last_telemetry["request_attempts"] = attempt + 1
            self.last_telemetry["retry_count"] = attempt
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    self.last_telemetry["response_status"] = getattr(response, "status", None)
                    return self._read_response(response, service)
            except GoogleAPIError:
                raise
            except urllib.error.HTTPError as exc:
                if self._retry_http_error(exc, service, attempt, api_key, access_token):
                    continue
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, 4))
                    continue
                raise GoogleAPIError(
                    service,
                    None,
                    "network request was unavailable",
                    state="BLOCKED",
                ) from exc
        raise GoogleAPIError(
            service,
            None,
            "retry budget exhausted",
            state="BLOCKED",
        )

    @staticmethod
    def _safe_error_message(exc: urllib.error.HTTPError) -> str:
        try:
            raw = exc.read(64_001)
            if len(raw) > 64_000:
                return "provider error body exceeds limit"
            payload = json.loads(raw.decode("utf-8"))
            message = (
                (payload.get("error") or {}).get("message")
                if isinstance(payload, dict)
                else None
            )
        except Exception:  # noqa: BLE001
            message = None
        return str(message or "provider rejected the request")[:1000]

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value:
            try:
                return max(0.0, min(float(value), 60.0))
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(value)
                    return max(0.0, min(parsed.timestamp() - time.time(), 60.0))
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(min(2**attempt, 8))
