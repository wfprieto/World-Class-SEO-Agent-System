"""Bounded public-web HTTP transport for technical SEO inspection.

This module reuses ``adapters.url_safety`` as the single target policy. Redirects
are followed manually so every hop is revalidated and chain evidence is retained.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from adapters.url_safety import validate_public_url


_REDIRECTS = {301, 302, 303, 307, 308}


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class HttpHop:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "headers": self.headers,
            "elapsed_ms": self.elapsed_ms,
        }


class BoundedHttpClient:
    """Read public HTTP(S) resources with bounded size, time and redirects."""

    def __init__(
        self,
        *,
        timeout: float = 30,
        max_response_bytes: int = 12_000_000,
        max_redirects: int = 10,
        opener: Any | None = None,
        user_agent: str = "World-Class-SEO-Technical/1.0",
    ) -> None:
        if timeout <= 0 or timeout > 120:
            raise ValueError("timeout must be greater than 0 and at most 120 seconds")
        if not isinstance(max_response_bytes, int) or not 1 <= max_response_bytes <= 50_000_000:
            raise ValueError("max_response_bytes must be from 1 to 50000000")
        if not isinstance(max_redirects, int) or not 0 <= max_redirects <= 20:
            raise ValueError("max_redirects must be an integer from 0 to 20")
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.opener = opener or urllib.request.build_opener(_NoRedirects())

    def get(self, url: str, **_: Any) -> HttpHop:
        """Return the final bounded response after validating every redirect hop."""
        safe = validate_public_url(url)
        current = safe
        visited: set[str] = set()
        for redirect_index in range(self.max_redirects + 1):
            if current in visited:
                raise ValueError("redirect loop detected")
            visited.add(current)
            hop = self._single_request(current)
            if hop.status_code not in _REDIRECTS:
                return hop
            location = self._header(hop.headers, "location")
            if not location:
                return hop
            if redirect_index >= self.max_redirects:
                raise ValueError("redirect chain exceeds configured limit")
            current = validate_public_url(urllib.parse.urljoin(current, location))
        raise ValueError("redirect chain exceeds configured limit")

    def redirect_chain(self, url: str, *, max_redirects: int | None = None) -> dict[str, Any]:
        limit = self.max_redirects if max_redirects is None else max_redirects
        if not isinstance(limit, int) or not 0 <= limit <= 20:
            raise ValueError("max_redirects must be an integer from 0 to 20")
        current = validate_public_url(url)
        visited: set[str] = set()
        hops: list[dict[str, Any]] = []
        loop_detected = False
        limit_reached = False
        blocked_target: str | None = None
        final_url: str | None = None
        for redirect_index in range(limit + 1):
            if current in visited:
                loop_detected = True
                break
            visited.add(current)
            hop = self._single_request(current)
            hops.append(hop.as_dict())
            final_url = hop.final_url
            if hop.status_code not in _REDIRECTS:
                break
            location = self._header(hop.headers, "location")
            if not location:
                break
            candidate = urllib.parse.urljoin(current, location)
            try:
                next_url = validate_public_url(candidate)
            except ValueError:
                blocked_target = candidate
                break
            if next_url in visited:
                loop_detected = True
                break
            if redirect_index >= limit:
                limit_reached = True
                break
            current = next_url
        state = (
            "BLOCKED"
            if loop_detected or limit_reached or blocked_target
            else "AVAILABLE"
        )
        return {
            "requested_url": url,
            "final_url": final_url,
            "hops": hops,
            "hop_count": len(hops),
            "loop_detected": loop_detected,
            "limit_reached": limit_reached,
            "blocked_target": blocked_target,
            "data_state": state,
        }

    def _single_request(self, url: str) -> HttpHop:
        safe = validate_public_url(url)
        request = urllib.request.Request(
            safe,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",
            },
            method="GET",
        )
        started = time.monotonic()
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        try:
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > self.max_response_bytes:
                        raise ValueError("response exceeds maximum allowed size")
                except ValueError as exc:
                    if "exceeds" in str(exc):
                        raise
                    raise ValueError("invalid Content-Length header") from exc
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ValueError("response exceeds maximum allowed size")
            status = int(getattr(response, "status", None) or getattr(response, "code", 0) or 0)
            headers = {str(key): str(value) for key, value in response.headers.items()}
            final_url = str(getattr(response, "url", None) or getattr(response, "geturl", lambda: safe)())
            if final_url:
                final_url = validate_public_url(final_url)
            else:
                final_url = safe
            return HttpHop(
                requested_url=safe,
                final_url=final_url,
                status_code=status,
                headers=headers,
                body=body,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        lowered = name.lower()
        for key, value in headers.items():
            if key.lower() == lowered:
                return value
        return None
