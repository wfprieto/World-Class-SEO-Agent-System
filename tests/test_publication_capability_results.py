"""Clearly synthetic contract packets only: no actual capability execution evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from adapters.mcp_extensions import REGISTRY
from scripts.publication_capability_results import validate_result
from scripts.publication_subject import JsonObject

COMMANDS = ("google.gsc-query", "google.gsc-aggregate", "google.ga4-report", "render.page",
    "render.screenshot", "render.health", "links.commoncrawl", "domain.history",
    "media.youtube-search", "indexnow.validate", "indexnow.submit")
GSC_LIMITS = ["Search Analytics returns top rows and does not guarantee every dimension row.",
             "Dimension rows must not be summed to replace the separate aggregate totals."]


@pytest.mark.parametrize("command", ["render.page", "google.gsc-query"])
def test_reviewer_metadata_type_substitutions_are_rejected(command: str) -> None:
    payload = valid_result(command)
    data = payload["data"]
    assert isinstance(data, dict)
    if command == "render.page":
        data["status_code"] = True
    else:
        data["date_range"]["timezone"] = False
    with pytest.raises(ValueError):
        validate_result(command, payload)


def _google_data(command: str) -> JsonObject:
    data: JsonObject
    if command.startswith("google.gsc-"):
        data = {"site_url": "sc-domain:example.com", "aggregate": dict.fromkeys(
            ("clicks", "impressions", "ctr", "position"), 0.0), "aggregate_source": "dimensionless_aggregate_query",
            "rows": [], "row_count": 0, "dimensions": [], "date_range": {
                "start": "2026-10-01", "end": "2026-10-02", "timezone": "America/Los_Angeles"},
            "pagination": {"row_limit": 25000, "max_pages": 4, "detail_pages_requested": 0,
                           "rows_truncated": False}, "data_state": "EMPTY", "provider_data_state": "final",
            "search_type": "web", "aggregation_type": "auto", "provider_metadata": {
                "aggregate": {}, "detail_pages": []}, "request_metadata": [], "warnings": [],
            "limitations": list(GSC_LIMITS)}
    else:
        data = {"property": "properties/123", "date_range": {"start": "2026-10-01", "end": "2026-10-02"},
            "dimensions": ["country"], "metrics": [{"name": "sessions", "type": "TYPE_INTEGER"}],
            "rows": [], "row_count": 0, "returned_rows": 0, "offset": 0, "limit": 100,
            "totals": [], "totals_source": "ga4_metric_aggregation_total", "property_quota": None,
            "metadata": {}, "currency_code": None, "time_zone": None,
            "limitations": ["The API reports data collected by the configured GA4 property; missing events cannot be inferred as zero activity.",
                "Overlapping date ranges would duplicate overlapping event data; this connector issues one date range per call."]}
    return data


def _browser_data(command: str) -> JsonObject:
    if command == "render.health":
        data = {"dependency": "installed", "browser": "installed", "executable": "/synthetic/chromium",
            "state": "AVAILABLE", "install_command": "python -m playwright install chromium",
            "uninstall_command": "python -m playwright uninstall chromium"}
    else:
        data = {"url": "https://example.com/", "final_url": "https://example.com/", "rendered": True,
            "data_state": "AVAILABLE", "render_engine": "playwright-chromium", "render_ms": 5,
            "viewport": {"width": 1440, "height": 900}, "evidence": {
                "rendered_html": "VERIFIED", "screenshot": "NOT_RUN"}, "html": "<html></html>",
            "text": "", "title": "", "status_code": 200, "console_errors": [],
            "page_errors": [], "failed_requests": [], "network_policy": {"synthetic_only": True}}
        if command == "render.screenshot":
            data = {**data, "path": "/synthetic/capture.png", "bytes": 4, "full_page": False,
                    "evidence": {"rendered_html": "VERIFIED", "screenshot": "VERIFIED"}}
            for key in ("html", "text", "title"):
                data.pop(key)
    return data


def valid_result(command: str) -> JsonObject:
    """SYNTHETIC ONLY. Current Bing intentionally has no successful fixture."""
    if command not in COMMANDS:
        raise ValueError("No successful current-source synthetic fixture for this command")
    warnings: list[str] = []
    if command.startswith("google."):
        data = _google_data(command)
    elif command.startswith("render."):
        data = _browser_data(command)
    elif command == "links.commoncrawl":
        data = {"domain": "example.com", "index": "CC-MAIN-SYNTHETIC", "records": [], "record_count": 0,
            "request_count": 2, "retry_count": 0, "coverage": "bounded_url_index_sample", "data_state": "EMPTY"}
        warnings = ["Common Crawl URL-index presence is not a complete backlink graph and must not be presented as one."]
    elif command == "domain.history":
        data = {"domain": "example.com", "data_state": "AVAILABLE", "handle": None, "status": [],
            "events": {}, "nameservers": [], "secure_dns": None, "registrar": None, "notices": [],
            "rdap_conformance": [], "ownership_inference": None, "request_count": 2, "retry_count": 0}
        warnings = ["RDAP registration data may be redacted, incomplete, delayed, or inconsistent across registries.",
                    "Registrar and event data do not establish beneficial ownership or domain reputation."]
    elif command == "media.youtube-search":
        data = {"data_state": "EMPTY", "results": [], "result_count": 0, "next_page_token": None,
            "region_code": None, "provider_total_results_approximate": 0, "request_count": 1,
            "retry_count": 0, "quota_units_estimated": 1, "quota_bucket": "search.list"}
        warnings = ["YouTube pageInfo.totalResults is approximate and must not be used as an exact inventory count."]
    elif command == "indexnow.validate":
        data = {"state": "AVAILABLE", "host": "example.com", "url_count": 1,
            "urls": ["https://example.com/"], "key_location": None, "execute_required": True,
            "confirmation_phrase": "INDEXNOW_SUBMIT"}
        warnings = ["Validation does not prove that the key file is publicly reachable.",
                    "A successful submission only confirms receipt, not crawling or indexing."]
    elif command == "indexnow.submit":
        data = {"state": "AVAILABLE", "http_status": 200, "host": "example.com", "url_count": 1,
            "attempts": 1, "endpoint_host": "api.indexnow.org", "key_location": None, "response_excerpt": ""}
        warnings = ["HTTP 200/202 confirms receipt or pending key validation only; it does not prove crawling or indexing."]
    else:
        raise ValueError("No successful current-source synthetic fixture for this command")
    status = "empty" if command in {"links.commoncrawl", "media.youtube-search"} else "ok"
    return {"command": command, "status": status, "data": data, "warnings": warnings, "error": None}


def synthetic_bing_success() -> JsonObject:
    """COUNTERFACTUAL shape only; current REGISTRY explicitly rejects this packet."""
    source = REGISTRY["bing-webmaster"]
    return {"command": "bing.preflight", "status": "ok", "error": None, "warnings": [],
            "data": {"provider": source.id, "state": "AVAILABLE", "available": True,
                     "credentials": dict.fromkeys(source.env_vars, "set"),
                     "transport": source.transport, "auth_mode": source.auth_mode}}


def test_error_only_data_cannot_masquerade_as_successful_capability() -> None:
    with pytest.raises(ValueError):
        validate_result("google.gsc-query", {"command": "google.gsc-query", "status": "ok",
            "data": {"error": "denied"}, "warnings": [], "error": None})


@pytest.mark.parametrize("command", COMMANDS)
def test_source_shaped_synthetic_success_preserves_actual_data(command: str) -> None:
    packet = valid_result(command)
    assert validate_result(command, packet) == packet["data"]


@pytest.mark.parametrize("command", COMMANDS)
def test_error_only_or_unknown_data_denied_for_every_command(command: str) -> None:
    packet = valid_result(command)
    packet["data"] = {"error": "denied"}
    with pytest.raises(ValueError):
        validate_result(command, packet)


def test_bing_is_always_blocked_under_current_canonical_source_policy() -> None:
    with pytest.raises(ValueError, match="Bing source contract"):
        validate_result("bing.preflight", synthetic_bing_success())
    with pytest.raises(ValueError):
        valid_result("bing.preflight")


def test_counterfactual_bing_shape_does_not_change_current_source_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    original = REGISTRY["bing-webmaster"]
    with monkeypatch.context() as scoped:
        scoped.setitem(REGISTRY, "bing-webmaster", replace(original, live_state="CONFIGURABLE"))
        assert validate_result("bing.preflight", synthetic_bing_success())["available"] is True
    assert REGISTRY["bing-webmaster"] == original
    with pytest.raises(ValueError):
        validate_result("bing.preflight", synthetic_bing_success())


def _mutate(packet: JsonObject, path: str, value: object) -> None:
    cursor = packet
    pieces = path.split(".")
    for piece in pieces[:-1]:
        item = cursor[piece]
        assert isinstance(item, dict)
        cursor = item
    cursor[pieces[-1]] = value


@pytest.mark.parametrize("command,path,value", [
    ("google.gsc-query", "data.aggregate.clicks", True),
    ("google.gsc-query", "data.aggregate.ctr", float("nan")),
    ("google.gsc-query", "data.aggregate.position", -1),
    ("google.gsc-query", "data.row_count", 1),
    ("google.gsc-query", "data.data_state", []),
    ("google.gsc-query", "data.data_state", "PARTIAL"),
    ("google.gsc-query", "data.pagination.rows_truncated", True),
    ("google.gsc-query", "data.date_range.start", "2026-10-03"),
    ("google.gsc-query", "data.limitations", ["Invented complete coverage"]),
    ("google.gsc-aggregate", "data.dimensions", ["query"]),
    ("google.ga4-report", "data.returned_rows", 1),
    ("google.ga4-report", "data.limit", True),
    ("google.ga4-report", "data.totals_source", "sum_detail_rows"),
    ("google.ga4-report", "data.totals", [{"sessions": True}]),
    ("google.ga4-report", "data.totals", [{"sessions": "NaN"}]),
    ("google.ga4-report", "data.row_count", 10),
    ("render.page", "data.rendered", False),
    ("render.page", "data.html", ""),
    ("render.page", "data.viewport.width", True),
    ("render.page", "data.evidence.rendered_html", "UNKNOWN"),
    ("render.page", "data.final_url", "file:///etc/passwd"),
    ("render.screenshot", "data.bytes", 25000001),
    ("render.screenshot", "data.bytes", True),
    ("render.screenshot", "data.path", "capture.html"),
    ("render.health", "data.browser", "missing"),
    ("links.commoncrawl", "data.request_count", 0),
    ("links.commoncrawl", "data.retry_count", 2),
    ("links.commoncrawl", "data.coverage", "complete_backlink_graph"),
    ("domain.history", "data.ownership_inference", "Verified beneficial owner"),
    ("domain.history", "data.events", []),
    ("media.youtube-search", "data.result_count", True),
    ("media.youtube-search", "data.quota_units_estimated", 0),
    ("media.youtube-search", "data.quota_bucket", "free_unlimited"),
    ("indexnow.validate", "data.url_count", 2),
    ("indexnow.validate", "data.execute_required", False),
    ("indexnow.validate", "data.urls", ["https://other.example/"]),
    ("indexnow.submit", "data.http_status", 202),
    ("indexnow.submit", "data.http_status", True),
    ("indexnow.submit", "data.attempts", 7),
    ("indexnow.submit", "data.state", ["AVAILABLE"]),
    ("indexnow.submit", "data.indexed", True),
])
def test_rejects_inconsistent_missing_nonfinite_or_boolean_alias_data(
    command: str, path: str, value: object,
) -> None:
    packet = valid_result(command)
    _mutate(packet, path, value)
    with pytest.raises(ValueError):
        validate_result(command, packet)


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("change", ["status", "error", "warnings", "command", "extra"])
def test_exact_envelope_and_known_success_status_are_required(command: str, change: str) -> None:
    packet = valid_result(command)
    value = {"status": "success", "error": {"message": "denied"}, "warnings": [True],
             "command": "unknown.command", "extra": True}[change]
    packet[change] = value
    with pytest.raises(ValueError):
        validate_result(command, packet)


def test_202_remains_partial_receipt_not_indexing_and_unknown_commands_block() -> None:
    packet = valid_result("indexnow.submit")
    packet["status"] = "partial"
    _mutate(packet, "data.http_status", 202)
    _mutate(packet, "data.state", "PARTIAL")
    assert validate_result("indexnow.submit", packet)["state"] == "PARTIAL"
    with pytest.raises(ValueError):
        validate_result("unknown.command", packet)


def test_missing_source_field_and_non_json_metadata_are_rejected() -> None:
    packet = valid_result("google.ga4-report")
    data = packet["data"]
    assert isinstance(data, dict)
    data.pop("property_quota")
    with pytest.raises(ValueError):
        validate_result("google.ga4-report", packet)
    packet = valid_result("google.ga4-report")
    _mutate(packet, "data.metadata", {"extra": object()})
    with pytest.raises(ValueError):
        validate_result("google.ga4-report", packet)


def test_source_gsc_normalizer_preserves_dimensionless_totals_partial_and_nullable_position() -> None:
    from integrations.google.gsc_results import query_result

    aggregate = {"clicks": 1.0, "impressions": 10.0, "ctr": 0.1, "position": 2.0}
    for metadata, dimensions in (({}, []), ({"first_incomplete_date": "2026-10-02"}, ["query"])):
        rows = [{"dimensions": {"query": "synthetic"}, **aggregate, "position": None}] if dimensions else []
        result = query_result("SYNTHETIC-normalizer-only", "sc-domain:example.com", "2026-10-01",
            "2026-10-02", dimensions, 25000, 4, "all", "web", "auto", {"rows": [{}], "metadata": metadata},
            aggregate, rows, False, int(bool(dimensions)), [], [])
        command = "google.gsc-query" if dimensions else "google.gsc-aggregate"
        envelope = {"command": command, "status": result.status, "data": result.data,
                    "warnings": result.warnings, "error": None}
        assert validate_result(command, envelope) == result.data
        if dimensions:
            del result.data["rows"][0]["position"]
            with pytest.raises(ValueError):
                validate_result(command, envelope)


def test_source_ga4_normalizer_preserves_truthful_partial_metric_types() -> None:
    from integrations.google.ga4 import GoogleAnalyticsDataAdapter

    adapter = object.__new__(GoogleAnalyticsDataAdapter)  # No OAuth/client constructor or request.
    response = {"dimensionHeaders": [{"name": "country"}],
        "metricHeaders": [{"name": "sessions", "type": "TYPE_INTEGER"}],
        "rows": [{"dimensionValues": [{"value": "US"}], "metricValues": [{"value": "4"}]}],
        "totals": [{"metricValues": [{"value": "20"}]}], "rowCount": 10,
        "metadata": {"dataLossFromOtherRow": True}}
    result = adapter._report_result(response, "properties/123", "2026-10-01", "2026-10-02",
                                    ["country"], ["sessions"], 0, 1, None)
    envelope = {"command": "google.ga4-report", "status": result.status,
                "data": result.data, "warnings": result.warnings, "error": None}
    assert validate_result("google.ga4-report", envelope) == result.data


def test_source_youtube_optional_null_metadata_is_preserved() -> None:
    from integrations.authority_media.youtube_service import YouTubeSearchService

    result = YouTubeSearchService.normalize({"items": [{"id": {"videoId": "synthetic-video"},
        "snippet": {"thumbnails": None}}]}, source="SYNTHETIC-normalizer-only", requests=1, retries=0)
    envelope = {"command": "media.youtube-search", "status": result.status,
                "data": result.data, "warnings": result.warnings, "error": None}
    assert validate_result("media.youtube-search", envelope) == result.data
    del result.data["results"][0]["thumbnails"]
    with pytest.raises(ValueError):
        validate_result("media.youtube-search", envelope)


@pytest.mark.parametrize("http", [200, 202])
def test_source_indexnow_response_normalizer_preserves_receipt_only_status(http: int) -> None:
    from integrations.extensions.indexnow_result import response_result

    result = response_result(status_code=http, raw=b"synthetic-only", secret="synthetic-only",
        host="example.com", url_count=1, attempts=1, endpoint="https://api.indexnow.org/indexnow",
        key_location=None)
    envelope = {"command": "indexnow.submit", "status": result.status,
                "data": result.data, "warnings": result.warnings, "error": None}
    accepted = validate_result("indexnow.submit", envelope)
    assert accepted["http_status"] == http
    assert accepted["response_excerpt"] == "[REDACTED]"


@pytest.mark.parametrize("command", ["domain.history", "media.youtube-search", "indexnow.submit"])
def test_source_uncertainty_warnings_cannot_be_replaced_by_complete_claims(command: str) -> None:
    packet = valid_result(command)
    packet["warnings"] = ["Complete evidence and confirmed indexing."]
    with pytest.raises(ValueError):
        validate_result(command, packet)
