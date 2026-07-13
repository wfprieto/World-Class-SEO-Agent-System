"""Bounded live adapter for Google PageSpeed Insights and current CrUX data.

The adapter reuses the canonical public-target URL policy and the shared Google
JSON transport. API keys are sent in ``X-Goog-Api-Key`` headers, never query
strings, so provider errors, proxies, and logs do not receive credential URLs.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from adapters.base import AdapterNotConfigured, AdapterResult
from adapters.url_safety import validate_public_url
from integrations.google.client import GoogleAPIError, GoogleJsonClient

__all__ = [
    "CRUX_ENDPOINT",
    "PSI_ENDPOINT",
    "GoogleAPIError",
    "GooglePageSpeedLiveAdapter",
]

PSI_ENDPOINT = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
_ALLOWED_STRATEGIES = {"mobile": "PHONE", "desktop": "DESKTOP"}


class GooglePageSpeedLiveAdapter:
    name = "google_pagespeed_live"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        crux_api_key: str | None = None,
        timeout: float = 60,
        max_retries: int = 2,
        max_response_bytes: int = 12_000_000,
        sleep=None,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self._psi_api_key = api_key or os.environ.get("GOOGLE_PAGESPEED_API_KEY")
        self._crux_api_key = (
            crux_api_key
            or os.environ.get("GOOGLE_CRUX_API_KEY")
            or self._psi_api_key
        )
        client_kwargs: dict[str, Any] = {
            "allowed_hosts": {
                "pagespeedonline.googleapis.com",
                "chromeuxreport.googleapis.com",
            },
            "timeout": timeout,
            "max_retries": max_retries,
            "max_response_bytes": max_response_bytes,
        }
        if sleep is not None:
            client_kwargs["sleep"] = sleep
        self._client = client or GoogleJsonClient(**client_kwargs)

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
        normalized_strategy = strategy.lower()
        if normalized_strategy not in _ALLOWED_STRATEGIES:
            raise ValueError("strategy must be 'mobile' or 'desktop'")
        safe_url = self._validate_public_url(url)
        warnings: list[str] = []

        psi = self._request_json(
            PSI_ENDPOINT,
            params={
                "url": safe_url,
                "strategy": normalized_strategy,
                "category": "performance",
            },
            api_key=self._psi_api_key,
        )
        data = self._parse_psi(psi, warnings)
        data.update(
            {
                "url": safe_url,
                "strategy": normalized_strategy,
                "crux_form_factor": _ALLOWED_STRATEGIES[normalized_strategy],
                "schema_version": "google_pagespeed_live.v3",
                "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "credential_transport": "X-Goog-Api-Key header",
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
                    params={},
                    api_key=self._crux_api_key,
                    post_body={
                        "url": safe_url,
                        "formFactor": _ALLOWED_STRATEGIES[normalized_strategy],
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
        return AdapterResult(
            source=self.name,
            status=status,
            data=data,
            warnings=warnings,
        )

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
        params: dict[str, str | int | None],
        post_body: dict[str, Any] | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        if endpoint not in {PSI_ENDPOINT, CRUX_ENDPOINT}:
            raise ValueError("endpoint is not an approved Google API endpoint")
        if not api_key:
            raise AdapterNotConfigured("A Google API key is required.")
        return self._client.request(
            endpoint,
            service=("crux" if endpoint == CRUX_ENDPOINT else "pagespeed"),
            method="POST" if post_body is not None else "GET",
            payload=post_body,
            api_key=api_key,
            query=params,
        )

    def _redact_secrets(self, message: str) -> str:
        redacted = message
        for secret in {self._psi_api_key, self._crux_api_key}:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted

    @staticmethod
    def _validate_public_url(url: str) -> str:
        """Delegate to the kit's single canonical URL-safety policy."""
        return validate_public_url(url)
