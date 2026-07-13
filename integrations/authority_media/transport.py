"""Bounded HTTPS transport for public authority and media evidence sources."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class TransportError(RuntimeError):
    """Sanitized transport failure."""


class ResponseTooLarge(TransportError):
    """Response exceeded the configured byte ceiling."""


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    url: str
    headers: dict[str, str]
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BoundedTransport:
    """Exact-host HTTPS client with bounded retries and response sizes."""

    def __init__(
        self,
        allowed_hosts: set[str] | frozenset[str],
        *,
        timeout_seconds: float = 15.0,
        max_response_bytes: int = 2_000_000,
        max_attempts: int = 3,
        opener: Any | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        hosts = {str(host).strip().lower().rstrip(".") for host in allowed_hosts if str(host).strip()}
        if not hosts:
            raise ValueError("allowed_hosts must contain at least one host")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be from 1 to 5")
        if not 1 <= max_response_bytes <= 20_000_000:
            raise ValueError("max_response_bytes must be from 1 to 20000000")
        self.allowed_hosts = frozenset(hosts)
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = int(max_response_bytes)
        self.max_attempts = int(max_attempts)
        self._opener = opener or urllib.request.build_opener(_NoRedirect())
        self._sleep = sleeper
        self.request_count = 0
        self.retry_count = 0

    def _validate_url(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("transport URL must use HTTPS and include a host")
        if parsed.username or parsed.password:
            raise ValueError("transport URL must not contain credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host not in self.allowed_hosts:
            raise ValueError(f"transport host is not approved: {host}")
        if parsed.port not in (None, 443):
            raise ValueError("transport URL must use the default HTTPS port")
        return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _safe_message(exc: BaseException) -> str:
        if isinstance(exc, urllib.error.HTTPError):
            return f"HTTP {exc.code} from approved provider"
        if isinstance(exc, (socket.timeout, TimeoutError)):
            return "approved provider request timed out"
        return "approved provider request failed"

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        accepted_statuses: set[int] | frozenset[int] = frozenset({200}),
    ) -> TransportResponse:
        safe_url = self._validate_url(url)
        clean_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
        last_error: BaseException | None = None
        for attempt in range(self.max_attempts):
            self.request_count += 1
            request = urllib.request.Request(
                safe_url,
                method="GET",
                headers={"Accept": "application/json, application/x-ndjson, text/plain;q=0.9", **clean_headers},
            )
            try:
                with self._opener.open(request, timeout=self.timeout_seconds) as response:
                    status = int(getattr(response, "status", response.getcode()))
                    if status not in accepted_statuses:
                        raise urllib.error.HTTPError(safe_url, status, "unexpected status", response.headers, None)
                    body = response.read(self.max_response_bytes + 1)
                    if len(body) > self.max_response_bytes:
                        raise ResponseTooLarge("approved provider response exceeded the byte ceiling")
                    final_url = self._validate_url(response.geturl())
                    return TransportResponse(
                        status_code=status,
                        url=final_url,
                        headers={str(k).lower(): str(v) for k, v in response.headers.items()},
                        body=body,
                    )
            except urllib.error.HTTPError as exc:
                if exc.code in accepted_statuses:
                    body = exc.read(self.max_response_bytes + 1)
                    if len(body) > self.max_response_bytes:
                        raise ResponseTooLarge("approved provider response exceeded the byte ceiling") from None
                    return TransportResponse(
                        status_code=int(exc.code),
                        url=safe_url,
                        headers={str(k).lower(): str(v) for k, v in (exc.headers or {}).items()},
                        body=body,
                    )
                last_error = exc
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
            except (OSError, TimeoutError, TransportError) as exc:
                if isinstance(exc, ResponseTooLarge):
                    raise
                last_error = exc
                retryable = True
            if not retryable or attempt + 1 >= self.max_attempts:
                break
            self.retry_count += 1
            self._sleep(min(0.25 * (2**attempt), 1.0))
        raise TransportError(self._safe_message(last_error or RuntimeError("request failed")))

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        accepted_statuses: set[int] | frozenset[int] = frozenset({200}),
    ) -> tuple[Any, TransportResponse]:
        response = self.get(url, headers=headers, accepted_statuses=accepted_statuses)
        if response.status_code == 404:
            return None, response
        try:
            value = json.loads(response.body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("approved provider returned invalid JSON") from exc
        if not isinstance(value, (dict, list)):
            raise TransportError("approved provider JSON must be an object or array")
        return value, response

    def get_text(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        accepted_statuses: set[int] | frozenset[int] = frozenset({200}),
    ) -> tuple[str, TransportResponse]:
        response = self.get(url, headers=headers, accepted_statuses=accepted_statuses)
        try:
            return response.body.decode("utf-8-sig"), response
        except UnicodeDecodeError as exc:
            raise TransportError("approved provider returned invalid UTF-8") from exc
