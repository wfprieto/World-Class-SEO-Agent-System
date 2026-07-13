"""Bounded Google API transport with scoped OAuth and sanitized failures.

This module supports Google-owned JSON APIs only. It is not a generic URL
fetcher and therefore does not replace ``adapters/url_safety.py``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any


_TRUTH_STATES = {
    "AVAILABLE",
    "PARTIAL",
    "EMPTY",
    "NOT_CONFIGURED",
    "UNAUTHORIZED",
    "RATE_LIMITED",
    "NOT_FOUND",
    "INVALID_RESPONSE",
    "BLOCKED",
    "FAILED",
}


def _state_for_status(status: int | None) -> str:
    if status in {401, 403}:
        return "UNAUTHORIZED"
    if status == 404:
        return "NOT_FOUND"
    if status == 429:
        return "RATE_LIMITED"
    if status is None:
        return "BLOCKED"
    return "FAILED"


class GoogleAPIError(RuntimeError):
    """Sanitized provider failure with an explicit truthful state."""

    def __init__(
        self,
        service: str,
        status: int | None,
        message: str,
        *,
        state: str | None = None,
    ) -> None:
        self.service = service
        self.status = status
        self.state = state or _state_for_status(status)
        if self.state not in _TRUTH_STATES:
            raise ValueError(f"unsupported Google API error state: {self.state}")
        super().__init__(
            f"{service} request failed"
            + (f" ({status})" if status is not None else "")
            + f": {message}"
        )


class _NoCrossHostRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = set(allowed_hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        original = urllib.parse.urlsplit(req.full_url)
        redirected = urllib.parse.urlsplit(newurl)
        if (
            redirected.scheme != "https"
            or redirected.hostname not in self.allowed_hosts
            or redirected.hostname != original.hostname
        ):
            raise GoogleAPIError(
                "google_api",
                code,
                "refused redirect outside the original approved Google host",
                state="BLOCKED",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class GoogleOAuthConfig:
    access_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    token_uri: str = "https://oauth2.googleapis.com/token"

    @classmethod
    def from_env(cls, prefix: str) -> "GoogleOAuthConfig":
        normalized = prefix.upper().rstrip("_")
        return cls(
            access_token=os.getenv(f"{normalized}_ACCESS_TOKEN"),
            client_id=os.getenv(f"{normalized}_CLIENT_ID"),
            client_secret=os.getenv(f"{normalized}_CLIENT_SECRET"),
            refresh_token=os.getenv(f"{normalized}_REFRESH_TOKEN"),
            token_uri=os.getenv(
                f"{normalized}_TOKEN_URI",
                "https://oauth2.googleapis.com/token",
            ),
        )


class GoogleOAuthProvider:
    """Provide one scoped access token without storing it in repository state."""

    _ALLOWED_TOKEN_HOSTS = {"oauth2.googleapis.com"}

    def __init__(
        self,
        config: GoogleOAuthConfig,
        *,
        timeout: float = 30,
        max_response_bytes: int = 1_000_000,
        opener: Any | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not isinstance(max_response_bytes, int) or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.config = config
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self.opener = opener or urllib.request.build_opener(
            _NoCrossHostRedirects(self._ALLOWED_TOKEN_HOSTS)
        )

    def token(self) -> str:
        if self.config.access_token:
            return self.config.access_token
        if not all(
            [
                self.config.client_id,
                self.config.client_secret,
                self.config.refresh_token,
            ]
        ):
            raise GoogleAPIError(
                "google_oauth",
                None,
                "configure an access token or client ID, client secret, and refresh token",
                state="NOT_CONFIGURED",
            )
        parsed = urllib.parse.urlsplit(self.config.token_uri)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self._ALLOWED_TOKEN_HOSTS
            or parsed.username
            or parsed.password
        ):
            raise GoogleAPIError(
                "google_oauth",
                None,
                "token endpoint must be the approved HTTPS Google OAuth host",
                state="BLOCKED",
            )
        form = urllib.parse.urlencode(
            {
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": self.config.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.config.token_uri,
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                declared = response.headers.get("Content-Length")
                if declared:
                    try:
                        if int(declared) > self.max_response_bytes:
                            raise GoogleAPIError(
                                "google_oauth",
                                getattr(response, "status", None),
                                "token response exceeds size limit",
                                state="INVALID_RESPONSE",
                            )
                    except ValueError as exc:
                        raise GoogleAPIError(
                            "google_oauth",
                            getattr(response, "status", None),
                            "invalid Content-Length header",
                            state="INVALID_RESPONSE",
                        ) from exc
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise GoogleAPIError(
                        "google_oauth",
                        getattr(response, "status", None),
                        "token response exceeds size limit",
                        state="INVALID_RESPONSE",
                    )
                payload = json.loads(raw.decode("utf-8"))
        except GoogleAPIError:
            raise
        except urllib.error.HTTPError as exc:
            raise GoogleAPIError(
                "google_oauth",
                exc.code,
                "token refresh was rejected; verify credentials and account access",
                state="UNAUTHORIZED" if exc.code in {400, 401, 403} else _state_for_status(exc.code),
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GoogleAPIError(
                "google_oauth",
                None,
                "token refresh was unavailable; verify network access",
                state="BLOCKED",
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GoogleAPIError(
                "google_oauth",
                None,
                "token endpoint returned invalid JSON",
                state="INVALID_RESPONSE",
            ) from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise GoogleAPIError(
                "google_oauth",
                None,
                "token response did not include an access token",
                state="INVALID_RESPONSE",
            )
        return token


class GoogleJsonClient:
    """GET or POST bounded JSON requests to explicitly approved Google hosts."""

    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        timeout: float = 60,
        max_retries: int = 2,
        max_response_bytes: int = 12_000_000,
        opener: Any | None = None,
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
        request = urllib.request.Request(
            request_url,
            data=body,
            headers=headers,
            method=normalized_method,
        )
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
            except GoogleAPIError:
                raise
            except urllib.error.HTTPError as exc:
                self.last_telemetry["response_status"] = exc.code
                self.last_telemetry["rate_limited"] = exc.code == 429
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    self.sleep(self._retry_delay(exc.headers.get("Retry-After"), attempt))
                    continue
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
