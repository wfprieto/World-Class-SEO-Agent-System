"""Bounded live adapter for Google PageSpeed Insights and the CrUX API.

Canonical target: ``adapters/google_pagespeed_live.py``. The adapter supplies
normalized lab and optional field evidence to Core Web Vitals workflows through
the host repository's ``AdapterResult`` contract. Current Google API
documentation is authoritative for endpoints, accepted form factors, metrics,
quotas, and response semantics.

The adapter analyzes only an explicitly supplied public HTTP(S) URL, rejects
credential-bearing or non-public targets, restricts outbound requests and
redirects to exact approved Google hosts, bounds retries and response size, and
redacts configured API keys from surfaced errors. Lab data diagnoses; field
data represents eligible CrUX observations. Neither source alone proves a
ranking cause or a successful production remediation.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections.abc import Callable
from typing import Any

from adapters.url_safety import validate_public_url
from adapters.base import AdapterNotConfigured, AdapterResult


__all__ = [
    "CRUX_ENDPOINT",
    "PSI_ENDPOINT",
    "GoogleAPIError",
    "GooglePageSpeedLiveAdapter",
]

PSI_ENDPOINT = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_STRATEGIES = {"mobile": "PHONE", "desktop": "DESKTOP"}
_ALLOWED_TARGET_PORTS = frozenset({80, 443})
_HTTP_TIMEOUT = 60
_MAX_RESPONSE_BYTES = 12_000_000
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "code",
        "password",
        "passwd",
        "session",
        "sessionid",
        "token",
    }
)


class GoogleAPIError(RuntimeError):
    """Sanitized Google API failure with no credential-bearing URL."""

    def __init__(self, service: str, status: int | None, message: str) -> None:
        self.service = service
        self.status = status
        super().__init__(f"{service} request failed" + (f" ({status})" if status else "") + f": {message}")


class _GoogleRedirectHandler(urllib.request.HTTPRedirectHandler):
    allowed_hosts = frozenset(
        {"pagespeedonline.googleapis.com", "chromeuxreport.googleapis.com"}
    )

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        original = urllib.parse.urlsplit(req.full_url)
        redirected = urllib.parse.urlsplit(newurl)
        if (
            redirected.scheme != "https"
            or redirected.hostname not in self.allowed_hosts
            or redirected.hostname != original.hostname
        ):
            raise GoogleAPIError(
                "google_api", code, "refused redirect outside the original approved Google host"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GooglePageSpeedLiveAdapter:
    name = "google_pagespeed_live"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        crux_api_key: str | None = None,
        timeout: float = _HTTP_TIMEOUT,
        max_retries: int = 2,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be an integer from 0 to 5")
        if not isinstance(max_response_bytes, int) or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self._timeout = float(timeout)
        self._max_retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._sleep = sleep
        self._opener = urllib.request.build_opener(_GoogleRedirectHandler())
        self._psi_api_key = api_key or os.environ.get("GOOGLE_PAGESPEED_API_KEY")
        self._crux_api_key = (
            crux_api_key
            or os.environ.get("GOOGLE_CRUX_API_KEY")
            or self._psi_api_key
        )

    def fetch(
        self,
        url: str,
        strategy: str = "mobile",
        *,
        include_crux: bool = True,
        **_: Any,
    ) -> AdapterResult:
        if not self._psi_api_key:
            raise AdapterNotConfigured("GOOGLE_PAGESPEED_API_KEY is not set.")
        if not isinstance(strategy, str):
            raise TypeError("strategy must be a string")
        if not isinstance(include_crux, bool):
            raise TypeError("include_crux must be a bool")
        strategy = strategy.lower()
        if strategy not in _ALLOWED_STRATEGIES:
            raise ValueError("strategy must be 'mobile' or 'desktop'")
        safe_url = self._validate_public_url(url)
        warnings: list[str] = []
        psi = self._request_json(
            PSI_ENDPOINT,
            params={
                "url": safe_url,
                "strategy": strategy,
                "category": "performance",
                "key": self._psi_api_key,
            },
        )
        data = self._parse_psi(psi, warnings)
        data.update(
            {
                "url": safe_url,
                "strategy": strategy,
                "crux_form_factor": _ALLOWED_STRATEGIES[strategy],
                "schema_version": "google_pagespeed_live.v2",
                "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        if not include_crux:
            data["crux_status"] = "skipped"
            data["crux_field"] = None
        elif not self._crux_api_key:
            data["crux_status"] = "not_configured"
            data["crux_field"] = None
            warnings.append("CrUX skipped because no CrUX-capable API key is configured.")
        else:
            try:
                crux = self._request_json(
                    CRUX_ENDPOINT,
                    params={"key": self._crux_api_key},
                    post_body={
                        "url": safe_url,
                        "formFactor": _ALLOWED_STRATEGIES[strategy],
                        "metrics": [
                            "largest_contentful_paint",
                            "interaction_to_next_paint",
                            "cumulative_layout_shift",
                            "experimental_time_to_first_byte",
                        ],
                    },
                )
                data["crux_field"] = self._parse_crux(crux)
                data["crux_status"] = "available"
            except GoogleAPIError as exc:
                data["crux_field"] = None
                if exc.status == 404:
                    data["crux_status"] = "not_found"
                    warnings.append(
                        "CrUX has no eligible field record for this URL and form factor."
                    )
                else:
                    data["crux_status"] = "unavailable"
                    warnings.append(f"CrUX field request unavailable: {exc}")
            except (TypeError, ValueError) as exc:
                data["crux_field"] = None
                data["crux_status"] = "invalid_response"
                warnings.append(f"CrUX response could not be normalized: {exc}")

        has_valid_lab = (
            data.get("performance_score") is not None
            and data.get("runtime_error") is None
        )
        crux_complete = data.get("crux_status") in {"available", "skipped"}
        status = "ok" if has_valid_lab and crux_complete else "partial"
        return AdapterResult(source=self.name, status=status, data=data, warnings=warnings)

    @staticmethod
    def _parse_psi(psi: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        lighthouse = psi.get("lighthouseResult") or {}
        categories = lighthouse.get("categories") or {}
        audits = lighthouse.get("audits") or {}
        if not lighthouse:
            warnings.append("PageSpeed response did not contain lighthouseResult.")

        def numeric(audit_id: str) -> Any:
            return (audits.get(audit_id) or {}).get("numericValue")

        score = (categories.get("performance") or {}).get("score")
        runtime_error = lighthouse.get("runtimeError") or None
        run_warnings = lighthouse.get("runWarnings") or []
        if runtime_error:
            warnings.append(
                "Lighthouse runtime error: "
                + str(runtime_error.get("code") or "unknown")
            )
        if run_warnings:
            warnings.append(f"Lighthouse reported {len(run_warnings)} run warning(s).")
        return {
            "performance_score": round(float(score) * 100) if score is not None else None,
            "lab_lcp_ms": numeric("largest-contentful-paint"),
            "lab_cls": numeric("cumulative-layout-shift"),
            "lab_tbt_ms": numeric("total-blocking-time"),
            "lab_ttfb_ms": numeric("server-response-time"),
            "requested_url": lighthouse.get("requestedUrl"),
            "final_url": lighthouse.get("finalUrl"),
            "fetch_time": lighthouse.get("fetchTime"),
            "lighthouse_version": lighthouse.get("lighthouseVersion"),
            "analysis_utc_timestamp": psi.get("analysisUTCTimestamp"),
            "runtime_error": runtime_error,
            "run_warnings": run_warnings,
        }

    @staticmethod
    def _parse_crux(crux: dict[str, Any]) -> dict[str, Any]:
        record = crux.get("record") or {}
        metrics = record.get("metrics") or {}

        def p75(metric: str) -> Any:
            value = ((metrics.get(metric) or {}).get("percentiles") or {}).get("p75")
            if value is None:
                return None
            return float(value) if metric == "cumulative_layout_shift" else int(value)

        key = record.get("key") or {}
        return {
            "lcp_p75_ms": p75("largest_contentful_paint"),
            "inp_p75_ms": p75("interaction_to_next_paint"),
            "cls_p75": p75("cumulative_layout_shift"),
            "ttfb_p75_ms": p75("experimental_time_to_first_byte"),
            "record_key": key,
            "form_factor": key.get("formFactor"),
            "collection_period": record.get("collectionPeriod"),
            "url_normalization": crux.get("urlNormalizationDetails"),
        }

    def _request_json(
        self,
        endpoint: str,
        *,
        params: dict[str, str | None],
        post_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if endpoint not in {PSI_ENDPOINT, CRUX_ENDPOINT}:
            raise ValueError("endpoint is not an approved Google API endpoint")
        parsed_endpoint = urllib.parse.urlsplit(endpoint)

        clean_params = {key: value for key, value in params.items() if value is not None}
        request_url = endpoint + "?" + urllib.parse.urlencode(clean_params)
        body = (
            json.dumps(post_body, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if post_body is not None
            else None
        )
        request = urllib.request.Request(
            request_url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST" if body is not None else "GET",
        )
        service = "crux" if parsed_endpoint.hostname == "chromeuxreport.googleapis.com" else "pagespeed"

        for attempt in range(self._max_retries + 1):
            try:
                with self._opener.open(request, timeout=self._timeout) as response:
                    declared = response.headers.get("Content-Length")
                    if declared:
                        try:
                            declared_bytes = int(declared)
                        except ValueError as exc:
                            raise GoogleAPIError(
                                service, response.status, "invalid Content-Length header"
                            ) from exc
                        if declared_bytes > self._max_response_bytes:
                            raise GoogleAPIError(
                                service, response.status, "response exceeds size limit"
                            )
                    raw = response.read(self._max_response_bytes + 1)
                    if len(raw) > self._max_response_bytes:
                        raise GoogleAPIError(service, response.status, "response exceeds size limit")
                    try:
                        decoded = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise GoogleAPIError(service, response.status, "invalid JSON response") from exc
                    if not isinstance(decoded, dict):
                        raise GoogleAPIError(service, response.status, "JSON response is not an object")
                    return decoded
            except urllib.error.HTTPError as exc:
                message = self._redact_secrets(self._safe_http_error_message(exc))
                if exc.code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    self._sleep(self._retry_delay(exc.headers.get("Retry-After"), attempt))
                    continue
                raise GoogleAPIError(service, exc.code, message) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < self._max_retries:
                    self._sleep(min(2**attempt, 4))
                    continue
                reason = getattr(exc, "reason", exc)
                raise GoogleAPIError(
                    service, None, self._redact_secrets(str(reason)[:300])
                ) from exc
        raise AssertionError("retry loop exited unexpectedly")

    def _redact_secrets(self, message: str) -> str:
        redacted = message
        for secret in {self._psi_api_key, self._crux_api_key}:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
                encoded = urllib.parse.quote(secret, safe="")
                redacted = redacted.replace(encoded, "[REDACTED]")
        return redacted

    @staticmethod
    def _safe_http_error_message(exc: urllib.error.HTTPError) -> str:
        try:
            raw = exc.read(64_001)
            if len(raw) > 64_000:
                return "error body exceeds limit"
            payload = json.loads(raw.decode("utf-8"))
            message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None)
            if message:
                return str(message)[:500]
        except Exception:
            pass
        return str(exc.reason)[:300]

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                try:
                    when = parsedate_to_datetime(retry_after)
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    return min(max((when - datetime.now(timezone.utc)).total_seconds(), 0.0), 30.0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(2**attempt, 4)

    @staticmethod
    def _validate_public_url(url: str) -> str:
        """Delegate to the kit's single canonical URL-safety policy."""
        return validate_public_url(url)

