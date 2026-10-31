"""Pure source-contract capability results; never execution or permission authority."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import date
from urllib.parse import urlsplit

from adapters.mcp_extensions import REGISTRY
from scripts.publication_policy import MAX_RECORD_BYTES
from scripts.publication_subject import JsonObject, exact_keys, object_value, string_value

_GSC_LIMITS = ["Search Analytics returns top rows and does not guarantee every dimension row.",
               "Dimension rows must not be summed to replace the separate aggregate totals."]
_GA4_LIMITS = ["The API reports data collected by the configured GA4 property; missing events cannot be inferred as zero activity.",
               "Overlapping date ranges would duplicate overlapping event data; this connector issues one date range per call."]


def _require(condition: bool, message: str = "Capability result contradicts its source contract") -> None:
    if not condition:
        raise ValueError(message)


def _strings(value: object) -> list[str]:
    _require(isinstance(value, list))
    assert isinstance(value, list)
    _require(all(isinstance(item, str) for item in value))
    return list(value)


def _rows(data: JsonObject, name: str, count: str) -> list[JsonObject]:
    rows = data.get(name)
    _require(isinstance(rows, list))
    assert isinstance(rows, list)
    _require(_integer(data.get(count)) == len(rows))
    return [object_value(row, name) for row in rows]


def _integer(value: object, minimum: int = 0, maximum: int | None = None) -> int:
    _require(type(value) is int)
    assert isinstance(value, int)
    _require(value >= minimum and (maximum is None or value <= maximum))
    return value


def _number(value: object, nonnegative: bool = False) -> None:
    _require(type(value) in {int, float})
    assert isinstance(value, (int, float))
    _require(not isinstance(value, float) or math.isfinite(value))
    _require(not nonnegative or value >= 0)


def _json(value: object) -> None:
    pending = [value]
    count = 0
    while pending:
        item = pending.pop()
        count += 1
        _require(count <= MAX_RECORD_BYTES, "Capability result exceeds bounded JSON complexity")
        if isinstance(item, dict):
            _require(all(isinstance(key, str) for key in item))
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, float):
            _require(math.isfinite(item))
        else:
            _require(item is None or type(item) in {str, int, bool})


def _url(value: object) -> str:
    text = string_value(value, "result URL")
    parsed = urlsplit(text)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.hostname))
    _require(not parsed.username and not parsed.password and not parsed.fragment)
    _require(not any(character.isspace() or ord(character) < 32 for character in text))
    return text  # Root independently canonicalizes target/redirect/request bindings, without DNS.


def _dates(value: object) -> None:
    window = object_value(value, "date range")
    dates = [string_value(window.get(key), key) for key in ("start", "end")]
    _require(all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", item) for item in dates))
    _require(date.fromisoformat(dates[0]) <= date.fromisoformat(dates[1]))


def _state(data: JsonObject, status: str, rows: list[JsonObject]) -> None:
    expected = ("ok", "AVAILABLE") if rows else ("empty", "EMPTY")
    _require((status, data.get("data_state")) == expected)


def _telemetry(data: JsonObject) -> None:
    requests = _integer(data.get("request_count"), 1)
    _integer(data.get("retry_count"), 0, requests - 1)


def _gsc(data: JsonObject, status: str, warnings: list[str], command: str) -> None:
    string_value(data.get("site_url"), "GSC property")
    _require(data.get("aggregate_source") == "dimensionless_aggregate_query")
    aggregate = object_value(data.get("aggregate"), "aggregate")
    for key in ("clicks", "impressions", "ctr", "position"):
        _number(aggregate.get(key), True)
    rows = _rows(data, "rows", "row_count")
    dimensions = _strings(data.get("dimensions"))
    _require(len(set(dimensions)) == len(dimensions))
    _require(set(dimensions) <= {"country", "device", "date", "hour", "page", "query", "searchAppearance"})
    _require(command != "google.gsc-aggregate" or not dimensions)
    _require(bool(dimensions) or not rows)
    for row in rows:
        _require({"clicks", "impressions", "ctr", "position"} <= set(row))
        values = object_value(row.get("dimensions"), "row dimensions")
        _require(set(values) == set(dimensions) and all(value is None or isinstance(value, str) for value in values.values()))
        for key in ("clicks", "impressions", "ctr", "position"):
            if key != "position" or row.get(key) is not None:
                _number(row.get(key), True)
    _gsc_metadata(data, status, warnings, rows, aggregate, dimensions)


def _gsc_metadata(data: JsonObject, status: str, warnings: list[str], rows: list[JsonObject],
                  aggregate: JsonObject, dimensions: list[str]) -> None:
    _dates(data.get("date_range"))
    _require(object_value(data["date_range"], "GSC date range").get("timezone") == "America/Los_Angeles")
    pagination = object_value(data.get("pagination"), "pagination")
    limit = _integer(pagination.get("row_limit"), 1, 25000)
    pages = _integer(pagination.get("max_pages"), 1, 100)
    detail = _integer(pagination.get("detail_pages_requested"), 0, pages)
    _require(type(pagination.get("rows_truncated")) is bool and len(rows) <= limit * pages)
    _require((detail > 0) == bool(dimensions))
    _require(not pagination["rows_truncated"] or (detail == pages and len(rows) == limit * pages))
    provider = object_value(data.get("provider_metadata"), "provider metadata")
    object_value(provider.get("aggregate"), "aggregate metadata")
    metadata = provider.get("detail_pages")
    _require(isinstance(metadata, list))
    assert isinstance(metadata, list)
    for item in metadata:
        object_value(item, "detail metadata")
    partial = bool(pagination["rows_truncated"] or provider["aggregate"] or metadata)
    state = data.get("data_state")
    _require(isinstance(state, str) and state in {"AVAILABLE", "EMPTY", "PARTIAL"})
    if state == "EMPTY":
        _require(not rows and all(value == 0 for value in aggregate.values()))
    else:
        _require(state == ("PARTIAL" if partial else "AVAILABLE"))
    _require(status == ("partial" if state == "PARTIAL" else "ok"))
    _require(_strings(data.get("warnings")) == warnings)
    _gsc_warnings(data, warnings, pagination["rows_truncated"], provider, dimensions)
    _require(_strings(data.get("limitations")) == _GSC_LIMITS)
    _require(isinstance(data.get("request_metadata"), list))


def _gsc_warnings(data: JsonObject, warnings: list[str], truncated: object,
                  provider: JsonObject, dimensions: list[str]) -> None:
    expected = []
    if truncated:
        expected.append("Dimension rows reached the configured pagination ceiling; aggregate totals remain valid but row coverage is partial.")
    if provider["aggregate"] or provider["detail_pages"]:
        expected.append("Search Console reported incomplete recent data; inspect provider metadata before comparison.")
    if dimensions:
        expected.append("Visible dimension rows can exclude anonymized or lower-volume data and must not be summed as property totals.")
    _require(warnings == expected)
    _require(data.get("provider_data_state") in ("final", "all", "hourly_all"))
    _require(data.get("search_type") in ("web", "image", "video", "news", "discover", "googleNews"))
    string_value(data.get("aggregation_type"), "GSC aggregation type")


_METRIC_FLOAT = {"TYPE_FLOAT", "TYPE_SECONDS", "TYPE_MILLISECONDS", "TYPE_MINUTES", "TYPE_HOURS",
                 "TYPE_STANDARD", "TYPE_CURRENCY", "TYPE_FEET", "TYPE_MILES", "TYPE_METERS", "TYPE_KILOMETERS"}


def _ga4_metrics(value: object, headers: dict[str, str]) -> None:
    metrics = object_value(value, "GA4 metrics")
    _require(set(metrics) == set(headers))
    for name, kind in headers.items():
        if kind == "TYPE_INTEGER":
            _require(type(metrics[name]) is int)
        elif kind in _METRIC_FLOAT:
            _number(metrics[name])
        else:
            raw = string_value(metrics[name], "untyped GA4 numeric metric")
            _require(math.isfinite(float(raw)))


def _ga4(data: JsonObject, status: str, warnings: list[str], _command: str) -> None:
    _require(re.fullmatch(r"properties/[0-9]+", string_value(data.get("property"), "GA4 property")) is not None)
    _dates(data.get("date_range"))
    dimensions = _strings(data.get("dimensions"))
    _require(bool(dimensions) and len(set(dimensions)) == len(dimensions))
    raw_headers = data.get("metrics")
    _require(isinstance(raw_headers, list) and bool(raw_headers))
    assert isinstance(raw_headers, list)
    headers: dict[str, str] = {}
    for raw in raw_headers:
        header = object_value(raw, "metric header")
        name = string_value(header.get("name"), "metric name")
        kind = header.get("type")
        _require(isinstance(kind, str) and kind in _METRIC_FLOAT | {"TYPE_INTEGER", ""} and name not in headers)
        assert isinstance(kind, str)
        headers[name] = kind
    rows = _rows(data, "rows", "returned_rows")
    _require(len(rows) <= _integer(data.get("limit"), 1, 250000))
    offset, total = _integer(data.get("offset")), _integer(data.get("row_count"))
    _require(not rows or offset + len(rows) <= total)
    for row in rows:
        values = object_value(row.get("dimensions"), "GA4 dimensions")
        _require(set(values) == set(dimensions) and all(value is None or isinstance(value, str) for value in values.values()))
        _ga4_metrics(row.get("metrics"), headers)
    _ga4_totals(data, headers, status, warnings, offset + len(rows) < total)


def _ga4_totals(data: JsonObject, headers: dict[str, str], status: str,
                warnings: list[str], more: bool) -> None:
    _require(data.get("totals_source") == "ga4_metric_aggregation_total")
    totals = data.get("totals")
    _require(isinstance(totals, list))
    assert isinstance(totals, list)
    for row in totals:
        _ga4_metrics(row, headers)
    metadata = object_value(data.get("metadata"), "GA4 metadata")
    partial = more or bool(metadata.get("dataLossFromOtherRow"))
    _require(status == ("partial" if partial else "ok"))
    expected = []
    if more:
        expected.append("The report contains additional rows; increase offset or paginate to retrieve them.")
    if metadata.get("dataLossFromOtherRow"):
        expected.append("Google Analytics reported data loss from the aggregated '(other)' row.")
    _require(warnings == expected)
    _require(_strings(data.get("limitations")) == _GA4_LIMITS)


def _browser(data: JsonObject, status: str, _warnings: list[str], command: str) -> None:
    _require(status == "ok" and data.get("rendered") is True and data.get("data_state") == "AVAILABLE")
    _url(data.get("url"))
    _url(data.get("final_url"))
    _require(data.get("render_engine") == "playwright-chromium")
    viewport = object_value(data.get("viewport"), "viewport")
    _integer(viewport.get("width"), 320, 7680)
    _integer(viewport.get("height"), 200, 4320)
    _number(data.get("render_ms"), True)
    evidence = object_value(data.get("evidence"), "render evidence")
    _require(evidence.get("rendered_html") == "VERIFIED")
    if command == "render.screenshot":
        _integer(data.get("bytes"), 4, 25000000)
        _require(string_value(data.get("path"), "screenshot path").lower().endswith(".png"))
        _require(type(data.get("full_page")) is bool and evidence.get("screenshot") == "VERIFIED")
    else:
        if data.get("status_code") is not None:
            _integer(data["status_code"], 0)
        _require(isinstance(data.get("html"), str) and bool(data["html"]))
        _require(isinstance(data.get("text"), str) and isinstance(data.get("title"), str))
        _require(all(len(str(data[key]).encode("utf-8")) <= 12000000 for key in ("html", "text")))
        _require(evidence.get("screenshot") == "NOT_RUN")
        for key in ("console_errors", "page_errors"):
            _strings(data.get(key))
        _require(isinstance(data.get("failed_requests"), list))
        object_value(data.get("network_policy"), "browser network policy")


def _health(data: JsonObject, status: str, _warnings: list[str], _command: str) -> None:
    _require(status == "ok" and data.get("state") == "AVAILABLE")
    _require(data.get("dependency") == "installed" and data.get("browser") == "installed")
    string_value(data.get("executable"), "installed Chromium executable")
    _require(data.get("install_command") == "python -m playwright install chromium")
    _require(data.get("uninstall_command") == "python -m playwright uninstall chromium")


def _commoncrawl(data: JsonObject, status: str, warnings: list[str], _command: str) -> None:
    string_value(data.get("domain"), "Common Crawl domain")
    string_value(data.get("index"), "crawl index")
    rows = _rows(data, "records", "record_count")
    _state(data, status, rows)
    _telemetry(data)
    _require(data.get("coverage") == "bounded_url_index_sample")
    _require(any("not a complete backlink graph" in item for item in warnings))
    urls = []
    for row in rows:
        _require({"url", "timestamp", "status", "mime", "digest", "filename", "offset", "length"} <= set(row))
        urls.append(_url(row.get("url")))
    _require(len(set(urls)) == len(urls))


def _domain(data: JsonObject, status: str, warnings: list[str], _command: str) -> None:
    _require(status == "ok" and data.get("data_state") == "AVAILABLE" and data.get("ownership_inference") is None)
    string_value(data.get("domain"), "RDAP domain")
    events = object_value(data.get("events"), "RDAP events")
    for dates in events.values():
        _strings(dates)
    _strings(data.get("nameservers"))
    _require(data.get("registrar") is None or isinstance(data.get("registrar"), dict))
    _require(isinstance(data.get("notices"), list))
    _rdap_notices(data["notices"])
    _require(warnings == ["RDAP registration data may be redacted, incomplete, delayed, or inconsistent across registries.",
        "Registrar and event data do not establish beneficial ownership or domain reputation."])
    _telemetry(data)


def _rdap_notices(value: object) -> None:
    _require(isinstance(value, list))
    assert isinstance(value, list)
    for item in value:
        notice = object_value(item, "RDAP notice")
        exact_keys(notice, {"title", "description"}, "RDAP notice")
        _require(notice["title"] is None or isinstance(notice["title"], str))
        description = notice["description"]
        if description is not None and not isinstance(description, str):
            _strings(description)


def _youtube(data: JsonObject, status: str, warnings: list[str], _command: str) -> None:
    rows = _rows(data, "results", "result_count")
    _state(data, status, rows)
    _telemetry(data)
    _require(_integer(data.get("quota_units_estimated"), 1) == data["request_count"])
    _require(data.get("quota_bucket") == "search.list")
    _require(warnings == ["YouTube pageInfo.totalResults is approximate and must not be used as an exact inventory count."])
    for row in rows:
        _require({"video_id", "title", "description", "channel_id", "channel_title", "published_at",
                  "live_broadcast_content", "thumbnails"} <= set(row))
        string_value(row.get("video_id"), "YouTube video identity")
        for key in ("title", "description", "channel_id", "channel_title", "published_at", "live_broadcast_content"):
            _require(row.get(key) is None or isinstance(row.get(key), str))
        _require(row.get("thumbnails") is None or isinstance(row.get("thumbnails"), dict))


def _indexnow(data: JsonObject, status: str, warnings: list[str], command: str) -> None:
    string_value(data.get("host"), "IndexNow host")
    count = _integer(data.get("url_count"), 1, 10000)
    if data.get("key_location") is not None:
        _require(urlsplit(_url(data["key_location"])).hostname == data["host"])
    if command == "indexnow.validate":
        _require(status == "ok" and data.get("state") == "AVAILABLE")
        urls = _strings(data.get("urls"))
        _require(len(urls) == len(set(urls)) == count)
        for value in urls:
            _require(urlsplit(_url(value)).hostname == data["host"])
        _require(data.get("execute_required") is True and data.get("confirmation_phrase") == "INDEXNOW_SUBMIT")
    else:
        http = _integer(data.get("http_status"), 200, 202)
        _require((http, status, data.get("state")) in ((200, "ok", "AVAILABLE"), (202, "partial", "PARTIAL")))
        _integer(data.get("attempts"), 1, 6)
        _require(data.get("endpoint_host") in ("api.indexnow.org", "www.bing.com"))
        _require(isinstance(data.get("response_excerpt"), str) and len(str(data["response_excerpt"])) <= 500)
        _require(not any(data.get(key) for key in ("indexed", "crawled", "indexing_confirmed")))
    expected = (["Validation does not prove that the key file is publicly reachable.",
                 "A successful submission only confirms receipt, not crawling or indexing."]
                if command == "indexnow.validate" else ["HTTP 200/202 confirms receipt or pending key validation only; it does not prove crawling or indexing."])
    _require(warnings == expected)


def _bing(data: JsonObject, status: str, _warnings: list[str], _command: str) -> None:
    source = REGISTRY["bing-webmaster"]
    _require(source.live_state == "CONFIGURABLE", "Current Bing source contract blocks publication")
    _require(status == "ok" and data.get("provider") == source.id and data.get("state") == "AVAILABLE")
    _require(data.get("available") is True and data.get("transport") == source.transport == "direct_api")
    credentials = object_value(data.get("credentials"), "credential presence states")
    _require(set(credentials) == set(source.env_vars) and all(state == "set" for state in credentials.values()))
    _require(data.get("auth_mode") == source.auth_mode)


_HANDLERS: dict[str, Callable[[JsonObject, str, list[str], str], None]] = {
    "google.gsc-query": _gsc, "google.gsc-aggregate": _gsc, "google.ga4-report": _ga4,
    "render.page": _browser, "render.screenshot": _browser, "render.health": _health,
    "links.commoncrawl": _commoncrawl, "domain.history": _domain,
    "media.youtube-search": _youtube, "indexnow.validate": _indexnow,
    "indexnow.submit": _indexnow, "bing.preflight": _bing,
}

_FIELDS = {
    "google.gsc-query": "site_url aggregate aggregate_source rows row_count dimensions date_range pagination data_state provider_data_state search_type aggregation_type provider_metadata request_metadata warnings limitations",
    "google.ga4-report": "property date_range dimensions metrics rows row_count returned_rows offset limit totals totals_source property_quota metadata currency_code time_zone limitations",
    "render.page": "url final_url html text title status_code console_errors page_errors failed_requests network_policy render_ms render_engine viewport rendered data_state evidence",
    "render.screenshot": "url final_url path bytes full_page viewport render_engine render_ms rendered data_state evidence",
    "render.health": "dependency browser executable state install_command uninstall_command",
    "links.commoncrawl": "data_state domain index records record_count request_count retry_count coverage",
    "domain.history": "data_state domain handle status events nameservers secure_dns registrar notices rdap_conformance ownership_inference request_count retry_count",
    "media.youtube-search": "data_state results result_count next_page_token region_code provider_total_results_approximate request_count retry_count quota_units_estimated quota_bucket",
    "indexnow.submit": "state http_status host url_count attempts endpoint_host key_location response_excerpt",
    "indexnow.validate": "state host url_count urls key_location execute_required confirmation_phrase",
    "bing.preflight": "provider state available credentials transport auth_mode",
}
_FIELDS["google.gsc-aggregate"] = _FIELDS["google.gsc-query"]


def validate_result(command: str, value: object) -> JsonObject:
    _require(isinstance(command, str) and command in _HANDLERS, "Unknown capability command")
    envelope = object_value(value, "capability result")
    exact_keys(envelope, {"command", "status", "data", "warnings", "error"}, "CLI result")
    _require(envelope["command"] == command and envelope["error"] is None)
    status = string_value(envelope["status"], "CLI status")
    warnings = _strings(envelope["warnings"])
    data = object_value(envelope["data"], "result data")
    _require(set(_FIELDS[command].split()) <= set(data), "Capability result is missing canonical source data")
    _json(envelope)
    _require(not data.get("error") and not data.get("errors"))
    _HANDLERS[command](data, status, warnings, command)
    return data
