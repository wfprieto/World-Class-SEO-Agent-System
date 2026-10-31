"""Neutral Google transport ports and identity-preserving provider errors."""

from __future__ import annotations

from typing import Any, Protocol

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


class JsonClient(Protocol):
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
        """Retrieve bounded provider JSON through the supplied transport."""


class TokenProvider(Protocol):
    def token(self) -> str:
        """Return a scoped access token or a truthful GoogleAPIError."""
