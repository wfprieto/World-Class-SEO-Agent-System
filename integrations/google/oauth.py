"""Scoped Google OAuth configuration and bounded token refresh."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.client import HTTPResponse

from contracts.google import GoogleAPIError, _state_for_status
from integrations.google.transport import _NoCrossHostRedirects


@dataclass(frozen=True)
class GoogleOAuthConfig:
    access_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    token_uri: str = "https://oauth2.googleapis.com/token"

    @classmethod
    def from_env(cls, prefix: str) -> GoogleOAuthConfig:
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
        opener: urllib.request.OpenerDirector | None = None,
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

    def _refresh_request(self) -> urllib.request.Request:
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
        return urllib.request.Request(
            self.config.token_uri,
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )

    def _read_token_response(self, response: HTTPResponse) -> object:
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
        return json.loads(raw.decode("utf-8"))

    def token(self) -> str:
        if self.config.access_token:
            return self.config.access_token
        request = self._refresh_request()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = self._read_token_response(response)
        except GoogleAPIError:
            raise
        except urllib.error.HTTPError as exc:
            try:
                raise GoogleAPIError(
                    "google_oauth",
                    exc.code,
                    "token refresh was rejected; verify credentials and account access",
                    state="UNAUTHORIZED" if exc.code in {400, 401, 403} else _state_for_status(exc.code),
                ) from exc
            finally:
                exc.close()
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
