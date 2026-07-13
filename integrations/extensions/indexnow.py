"""Bounded IndexNow validation and explicitly authorized submission."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from adapters.base import AdapterNotConfigured, AdapterResult

MAX_URLS = 10_000
MAX_RESPONSE_BYTES = 65_536
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
APPROVED_ENDPOINT_HOSTS = frozenset({"api.indexnow.org", "www.bing.com"})
_KEY = re.compile(r"^[A-Za-z0-9-]{8,128}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirects are not allowed", headers, fp)


@dataclass(frozen=True)
class NormalizedSubmission:
    host: str
    urls: tuple[str, ...]
    key_location: str | None


def _normalize_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("each URL must be a non-empty string")
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("IndexNow URLs must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    port = parsed.port
    default_port = 80 if parsed.scheme == "http" else 443
    if port not in {None, default_port}:
        raise ValueError("IndexNow URLs may not use non-standard ports")
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path or "/", parsed.query, ""))


def normalize(urls: Iterable[str], key_location: str | None = None) -> NormalizedSubmission:
    rows = tuple(dict.fromkeys(_normalize_url(value) for value in urls))
    if not rows:
        raise ValueError("at least one URL is required")
    if len(rows) > MAX_URLS:
        raise ValueError(f"IndexNow supports at most {MAX_URLS} URLs per request")
    hosts = {urllib.parse.urlsplit(value).hostname for value in rows}
    if len(hosts) != 1:
        raise ValueError("all submitted URLs must belong to one host")
    host = next(iter(hosts))
    assert host is not None
    normalized_location = None
    if key_location:
        normalized_location = _normalize_url(key_location)
        parsed_location = urllib.parse.urlsplit(normalized_location)
        if parsed_location.hostname != host:
            raise ValueError("keyLocation must use the same host as the submitted URLs")
        base_path = parsed_location.path.rsplit("/", 1)[0] + "/"
        if base_path != "/" and any(
            not urllib.parse.urlsplit(value).path.startswith(base_path) for value in rows
        ):
            raise ValueError("submitted URLs must fall under the keyLocation directory")
    return NormalizedSubmission(host=host, urls=rows, key_location=normalized_location)


def _validate_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" or parsed.hostname not in APPROVED_ENDPOINT_HOSTS:
        raise ValueError("IndexNow endpoint must use an approved HTTPS host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("IndexNow endpoint may not contain credentials, query, or fragment")
    if parsed.path.rstrip("/") != "/indexnow":
        raise ValueError("IndexNow endpoint path must be /indexnow")
    return urllib.parse.urlunsplit(("https", parsed.hostname, "/indexnow", "", ""))


class IndexNowService:
    def validate(self, *, urls: Iterable[str], key_location: str | None = None) -> AdapterResult:
        submission = normalize(urls, key_location)
        return AdapterResult(
            source="indexnow",
            status="ok",
            data={
                "state": "AVAILABLE",
                "host": submission.host,
                "url_count": len(submission.urls),
                "urls": list(submission.urls),
                "key_location": submission.key_location,
                "execute_required": True,
                "confirmation_phrase": "INDEXNOW_SUBMIT",
            },
            warnings=[
                "Validation does not prove that the key file is publicly reachable.",
                "A successful submission only confirms receipt, not crawling or indexing.",
            ],
        )

    def submit(
        self,
        *,
        urls: Iterable[str],
        key_location: str | None = None,
        key: str | None = None,
        execute: bool = False,
        confirmation: str = "",
        endpoint: str = INDEXNOW_ENDPOINT,
        opener: Callable[..., Any] | None = None,
        timeout: float = 15.0,
    ) -> AdapterResult:
        submission = normalize(urls, key_location)
        target = _validate_endpoint(endpoint)
        secret = key or os.environ.get("INDEXNOW_KEY")
        if not secret:
            raise AdapterNotConfigured("INDEXNOW_KEY is not configured")
        if not _KEY.fullmatch(secret):
            raise ValueError("IndexNow key must be 8-128 letters, numbers, or dashes")
        preview = {
            "state": "BLOCKED",
            "host": submission.host,
            "url_count": len(submission.urls),
            "urls": list(submission.urls),
            "key_location": submission.key_location,
            "endpoint_host": urllib.parse.urlsplit(target).hostname,
        }
        if not execute or confirmation != "INDEXNOW_SUBMIT":
            return AdapterResult(
                source="indexnow",
                status="blocked",
                data=preview,
                warnings=[
                    "No request was sent. Use --execute with --confirm INDEXNOW_SUBMIT after verifying ownership and the URL set."
                ],
            )

        payload: dict[str, Any] = {
            "host": submission.host,
            "key": secret,
            "urlList": list(submission.urls),
        }
        if submission.key_location:
            payload["keyLocation"] = submission.key_location
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            target,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "world-class-seo-agent-system/indexnow",
            },
        )
        active = opener or urllib.request.build_opener(NoRedirect()).open
        try:
            response = active(request, timeout=timeout)
            status_code = int(getattr(response, "status", response.getcode()))
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("IndexNow response exceeded the safe size limit")
        except urllib.error.HTTPError as exc:
            status_code = int(exc.code)
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
        state = {
            200: ("ok", "AVAILABLE"),
            202: ("partial", "PARTIAL"),
            400: ("invalid_response", "INVALID_RESPONSE"),
            403: ("unauthorized", "UNAUTHORIZED"),
            422: ("invalid_response", "INVALID_RESPONSE"),
            429: ("rate_limited", "RATE_LIMITED"),
        }.get(status_code, ("failed", "FAILED"))
        return AdapterResult(
            source="indexnow",
            status=state[0],
            data={
                "state": state[1],
                "http_status": status_code,
                "host": submission.host,
                "url_count": len(submission.urls),
                "endpoint_host": urllib.parse.urlsplit(target).hostname,
                "key_location": submission.key_location,
                "response_excerpt": raw.decode("utf-8", errors="replace").replace(secret, "[REDACTED]")[:500],
            },
            warnings=[
                "HTTP 200/202 confirms receipt or pending key validation only; it does not prove crawling or indexing."
            ],
        )


class IndexNowAdapter:
    name = "indexnow"

    def __init__(self) -> None:
        self.service = IndexNowService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        if operation == "validate":
            return self.service.validate(**kwargs)
        if operation == "submit":
            return self.service.submit(**kwargs)
        raise ValueError(f"unsupported IndexNow operation: {operation}")
