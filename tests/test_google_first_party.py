from __future__ import annotations

import io
import json
import urllib.error

import pytest

from integrations.google.client import (
    GoogleAPIError,
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)
from integrations.google.crux import (
    CrUXCurrentAdapter,
    CrUXHistoryAdapter,
    decompose_lcp_history,
)
from integrations.google.ga4 import GoogleAnalyticsDataAdapter
from integrations.google.gsc import GoogleSearchConsoleAdapter
from integrations.google.sitemaps import GoogleSitemapsAdapter


class FakeResponse:
    def __init__(self, payload, *, status=200, headers=None):
        if isinstance(payload, bytes):
            self.payload = payload
        else:
            self.payload = json.dumps(payload).encode("utf-8")
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


class CapturingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.last_telemetry = {
            "request_attempts": 1,
            "retry_count": 0,
            "response_status": 200,
            "rate_limited": False,
        }

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return self.responses.pop(0)


class RaisingClient:
    def __init__(self, error):
        self.error = error
        self.calls = []
        self.last_telemetry = {}

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        raise self.error


class TokenProvider:
    def __init__(self, token="token-value"):
        self.value = token
        self.calls = 0

    def token(self):
        self.calls += 1
        return self.value


def test_google_json_client_sends_api_key_in_header_not_url():
    opener = CapturingOpener([FakeResponse({"ok": True})])
    client = GoogleJsonClient(
        allowed_hosts={"chromeuxreport.googleapis.com"},
        opener=opener,
        max_retries=0,
    )
    result = client.request(
        "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord",
        service="crux_history",
        payload={"origin": "https://example.com"},
        api_key="top-secret-key",
    )
    assert result == {"ok": True}
    request, _ = opener.requests[0]
    assert "top-secret-key" not in request.full_url
    assert request.headers["X-goog-api-key"] == "top-secret-key"
    assert client.last_telemetry["request_attempts"] == 1


def test_google_json_client_retries_retryable_status_and_records_rate_limit():
    error = urllib.error.HTTPError(
        "https://chromeuxreport.googleapis.com/v1/x",
        429,
        "quota",
        {"Retry-After": "0"},
        io.BytesIO(json.dumps({"error": {"message": "quota denied"}}).encode()),
    )
    opener = CapturingOpener([error, FakeResponse({"ok": True})])
    delays = []
    client = GoogleJsonClient(
        allowed_hosts={"chromeuxreport.googleapis.com"},
        opener=opener,
        max_retries=1,
        sleep=delays.append,
    )
    assert client.request(
        "https://chromeuxreport.googleapis.com/v1/x",
        service="crux",
        api_key="secret-key",
    ) == {"ok": True}
    assert delays == [0.0]
    assert client.last_telemetry["retry_count"] == 1


def test_google_json_client_redacts_raw_and_encoded_credentials():
    token = "ya29.private/token"
    key = "AIza-private+key"
    error = urllib.error.HTTPError(
        "https://www.googleapis.com/webmasters/v3/sites/x",
        403,
        "forbidden",
        {},
        io.BytesIO(
            json.dumps(
                {
                    "error": {
                        "message": (
                            f"Bearer {token}; key {key}; encoded "
                            "ya29.private%2Ftoken"
                        )
                    }
                }
            ).encode()
        ),
    )
    client = GoogleJsonClient(
        allowed_hosts={"www.googleapis.com"},
        opener=CapturingOpener([error]),
        max_retries=0,
    )
    with pytest.raises(GoogleAPIError) as captured:
        client.request(
            "https://www.googleapis.com/webmasters/v3/sites/x",
            service="gsc",
            access_token=token,
            api_key=key,
        )
    message = str(captured.value)
    assert token not in message
    assert key not in message
    assert "ya29.private%2Ftoken" not in message
    assert captured.value.state == "UNAUTHORIZED"


def test_google_json_client_rejects_oversized_and_non_object_responses():
    oversized = FakeResponse(b"{" + b"x" * 101 + b"}", headers={"Content-Length": "103"})
    client = GoogleJsonClient(
        allowed_hosts={"www.googleapis.com"},
        opener=CapturingOpener([oversized]),
        max_retries=0,
        max_response_bytes=100,
    )
    with pytest.raises(GoogleAPIError) as captured:
        client.request("https://www.googleapis.com/x", service="gsc")
    assert captured.value.state == "INVALID_RESPONSE"

    client = GoogleJsonClient(
        allowed_hosts={"www.googleapis.com"},
        opener=CapturingOpener([FakeResponse([1, 2, 3])]),
        max_retries=0,
    )
    with pytest.raises(GoogleAPIError, match="not an object"):
        client.request("https://www.googleapis.com/x", service="gsc")


def test_oauth_supports_direct_token_and_bounds_refresh_response():
    assert GoogleOAuthProvider(
        GoogleOAuthConfig(access_token="direct-token")
    ).token() == "direct-token"

    provider = GoogleOAuthProvider(
        GoogleOAuthConfig(),
    )
    with pytest.raises(GoogleAPIError) as missing:
        provider.token()
    assert missing.value.state == "NOT_CONFIGURED"

    provider = GoogleOAuthProvider(
        GoogleOAuthConfig(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_uri="https://evil.example/token",
        )
    )
    with pytest.raises(GoogleAPIError, match="approved HTTPS Google OAuth host") as blocked:
        provider.token()
    assert blocked.value.state == "BLOCKED"

    provider = GoogleOAuthProvider(
        GoogleOAuthConfig(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
        ),
        opener=CapturingOpener([
            FakeResponse(
                {"access_token": "token"},
                headers={"Content-Length": "200"},
            )
        ]),
        max_response_bytes=100,
    )
    with pytest.raises(GoogleAPIError) as oversized:
        provider.token()
    assert oversized.value.state == "INVALID_RESPONSE"


def test_gsc_query_uses_dimensionless_aggregate_and_bounded_detail_pages():
    client = QueueClient([
        {
            "rows": [{"clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 4.2}],
            "responseAggregationType": "byProperty",
        },
        {
            "rows": [
                {"keys": ["query a"], "clicks": 30, "impressions": 300, "ctr": 0.1, "position": 3},
                {"keys": ["query b"], "clicks": 20, "impressions": 200, "ctr": 0.1, "position": 5},
            ]
        },
    ])
    token = TokenProvider()
    adapter = GoogleSearchConsoleAdapter(oauth=token, client=client)
    result = adapter.query(
        "sc-domain:example.com",
        "2026-06-01",
        "2026-06-30",
        dimensions=["query"],
        row_limit=100,
        max_pages=2,
        aggregation_type="byProperty",
    )
    assert result.status == "ok"
    assert result.data["aggregate"] == {
        "clicks": 100.0,
        "impressions": 1000.0,
        "ctr": 0.1,
        "position": 4.2,
    }
    assert sum(row["clicks"] for row in result.data["rows"]) == 50
    assert result.data["aggregate_source"] == "dimensionless_aggregate_query"
    assert result.data["data_state"] == "AVAILABLE"
    assert result.data["pagination"]["detail_pages_requested"] == 1
    assert "dimensions" not in client.calls[0][1]["payload"]
    assert client.calls[1][1]["payload"]["dimensions"] == ["query"]
    assert token.calls == 1


def test_gsc_aggregate_returns_no_detail_rows_and_empty_state_is_explicit():
    client = QueueClient([{}])
    result = GoogleSearchConsoleAdapter(
        oauth=TokenProvider(),
        client=client,
    ).aggregate(
        "sc-domain:example.com",
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    assert result.data["aggregate"] == {
        "clicks": 0.0,
        "impressions": 0.0,
        "ctr": 0.0,
        "position": 0.0,
    }
    assert result.data["rows"] == []
    assert result.data["dimensions"] == []
    assert result.data["data_state"] == "EMPTY"


def test_gsc_validation_and_url_inspection_preserve_provider_verdicts():
    adapter = GoogleSearchConsoleAdapter(oauth=TokenProvider(), client=QueueClient([]))
    with pytest.raises(ValueError, match="byProperty"):
        adapter.query(
            "sc-domain:example.com",
            dimensions=["page"],
            aggregation_type="byProperty",
        )
    with pytest.raises(ValueError, match="belong"):
        adapter.inspect("https://example.org/page", "sc-domain:example.com")

    client = QueueClient([
        {
            "inspectionResult": {
                "indexStatusResult": {
                    "verdict": "PASS",
                    "coverageState": "Submitted and indexed",
                    "indexingState": "INDEXING_ALLOWED",
                    "googleCanonical": "https://example.com/page",
                },
                "richResultsResult": {"verdict": "PASS"},
            }
        }
    ])
    result = GoogleSearchConsoleAdapter(
        oauth=TokenProvider(),
        client=client,
    ).inspect("https://www.example.com/page", "sc-domain:example.com")
    assert result.status == "ok"
    assert result.data["verdict"] == "PASS"
    assert result.data["indexing_state"] == "INDEXING_ALLOWED"
    assert result.data["provider_inspection_result"]["richResultsResult"]["verdict"] == "PASS"
    assert result.data["inspection_scope"] == "google_index_version_only"


def test_sitemaps_list_and_get_are_read_only_and_keep_errors_separate():
    list_client = QueueClient([
        {
            "sitemap": [
                {
                    "path": "https://example.com/sitemap.xml",
                    "lastSubmitted": "2026-06-30T12:00:00Z",
                    "warnings": "2",
                    "errors": "1",
                    "contents": [
                        {"type": "web", "submitted": "100", "indexed": "95"}
                    ],
                }
            ]
        }
    ])
    result = GoogleSitemapsAdapter(
        oauth=TokenProvider(),
        client=list_client,
    ).fetch("sc-domain:example.com")
    assert result.data["read_only"] is True
    assert result.data["warning_count"] == 2
    assert result.data["error_count"] == 1
    assert result.data["sitemaps"][0]["warning_count"] == 2
    assert list_client.calls[0][1]["method"] == "GET"
    assert list_client.calls[0][1].get("payload") is None

    get_client = QueueClient([
        {
            "path": "https://example.com/sitemap.xml",
            "warnings": "0",
            "errors": "0",
        }
    ])
    result = GoogleSitemapsAdapter(
        oauth=TokenProvider(),
        client=get_client,
    ).fetch(
        "sc-domain:example.com",
        sitemap_url="https://example.com/sitemap.xml",
    )
    assert result.data["operation"] == "get"
    assert result.data["sitemap_count"] == 1


def test_ga4_report_normalizes_rows_totals_quota_and_pagination():
    client = QueueClient([
        {
            "dimensionHeaders": [{"name": "landingPagePlusQueryString"}],
            "metricHeaders": [
                {"name": "sessions", "type": "TYPE_INTEGER"},
                {"name": "engagementRate", "type": "TYPE_FLOAT"},
            ],
            "rows": [
                {
                    "dimensionValues": [{"value": "/a"}],
                    "metricValues": [{"value": "12"}, {"value": "0.75"}],
                }
            ],
            "totals": [{"metricValues": [{"value": "50"}, {"value": "0.8"}]}],
            "rowCount": 2,
            "propertyQuota": {"tokensPerDay": {"remaining": 1000}},
            "metadata": {"dataLossFromOtherRow": True},
            "timeZone": "America/New_York",
        }
    ])
    adapter = GoogleAnalyticsDataAdapter(oauth=TokenProvider(), client=client)
    result = adapter.fetch(
        "1234",
        "2026-06-01",
        "2026-06-30",
        metrics=["sessions", "engagementRate"],
        limit=1,
    )
    assert result.status == "partial"
    assert result.data["property"] == "properties/1234"
    assert result.data["rows"][0]["metrics"] == {
        "sessions": 12,
        "engagementRate": 0.75,
    }
    assert result.data["totals"] == [{"sessions": 50, "engagementRate": 0.8}]
    assert result.data["totals_source"] == "ga4_metric_aggregation_total"
    assert result.data["property_quota"]["tokensPerDay"]["remaining"] == 1000
    assert any("additional rows" in item for item in result.warnings)
    assert any("data loss" in item for item in result.warnings)


def test_ga4_validates_property_names_and_current_key_event_terminology():
    adapter = GoogleAnalyticsDataAdapter(oauth=TokenProvider(), client=QueueClient([]))
    with pytest.raises(ValueError, match="property_id"):
        adapter.fetch("not-numeric")
    with pytest.raises(ValueError, match="invalid metric"):
        adapter.fetch("1234", metrics=["sessions;drop"])

    client = QueueClient([
        {
            "dimensionHeaders": [],
            "metricHeaders": [],
            "rows": [],
            "totals": [],
            "rowCount": 0,
        }
    ])
    GoogleAnalyticsDataAdapter(oauth=TokenProvider(), client=client).fetch(
        "1234", "2026-06-01", "2026-06-30"
    )
    names = [item["name"] for item in client.calls[0][1]["payload"]["metrics"]]
    assert names == ["sessions", "engagedSessions", "keyEvents"]


def test_crux_current_is_distinct_and_404_is_not_zero_performance():
    client = QueueClient([
        {
            "record": {
                "collectionPeriod": {
                    "firstDate": {"year": 2026, "month": 6, "day": 1},
                    "lastDate": {"year": 2026, "month": 6, "day": 28},
                },
                "metrics": {
                    "largest_contentful_paint": {
                        "percentiles": {"p75": 2300},
                        "histogram": [
                            {"start": 0, "end": 2500, "density": 0.8},
                        ],
                    }
                },
            }
        }
    ])
    result = CrUXCurrentAdapter(api_key="key", client=client).fetch(
        "https://example.com/page",
        metrics=["largest_contentful_paint"],
    )
    assert result.data["metrics"]["largest_contentful_paint"]["p75"] == 2300.0
    assert result.data["data_state"] == "AVAILABLE"
    assert "queryRecord" in client.calls[0][0]

    missing = CrUXCurrentAdapter(
        api_key="key",
        client=RaisingClient(
            GoogleAPIError("crux_current", 404, "not found", state="NOT_FOUND")
        ),
    ).fetch("https://example.com/page")
    assert missing.status == "not_found"
    assert missing.data["data_state"] == "NOT_FOUND"
    assert missing.data["metrics"] == {}


def test_crux_history_bounds_periods_parses_histograms_and_computes_lcp_parts():
    periods = [
        {"firstDate": {"year": 2026, "month": 6, "day": 1}, "lastDate": {"year": 2026, "month": 6, "day": 28}}
    ]
    metrics = {
        "largest_contentful_paint": {
            "percentilesTimeseries": {"p75s": [2500]},
            "histogramTimeseries": [
                {"start": 0, "end": 2500, "densities": [0.7]},
                {"start": 2500, "end": 4000, "densities": [0.2]},
                {"start": 4000, "densities": [0.1]},
            ],
        },
        "largest_contentful_paint_image_time_to_first_byte": {"percentilesTimeseries": {"p75s": [600]}},
        "largest_contentful_paint_image_resource_load_delay": {"percentilesTimeseries": {"p75s": [300]}},
        "largest_contentful_paint_image_resource_load_duration": {"percentilesTimeseries": {"p75s": [800]}},
        "largest_contentful_paint_image_element_render_delay": {"percentilesTimeseries": {"p75s": [700]}},
    }
    client = QueueClient([{"record": {"collectionPeriods": periods, "metrics": metrics}}])
    adapter = CrUXHistoryAdapter(api_key="key", client=client)
    result = adapter.fetch(
        "https://example.com/page",
        collection_period_count=40,
        metrics=list(metrics),
    )
    assert result.status == "ok"
    assert result.data["collection_period_count_requested"] == 40
    histogram = result.data["metrics"]["largest_contentful_paint"][0]["histogram"]
    assert histogram[0] == {"start": 0, "end": 2500, "density": 0.7}
    lcp = result.data["lcp_subparts"]
    assert lcp["evidence_state"] == "AVAILABLE"
    assert lcp["parts_complete"] is True
    assert lcp["parts_sum_ms"] == 2400
    assert lcp["lcp_minus_parts_ms"] == 100
    assert lcp["unit"] == "milliseconds"
    assert client.calls[0][1]["payload"]["collectionPeriodCount"] == 40

    with pytest.raises(ValueError, match="1 to 40"):
        adapter.fetch("https://example.com", collection_period_count=41)


def test_lcp_decomposition_never_estimates_missing_subparts():
    result = decompose_lcp_history({
        "largest_contentful_paint": [{"p75": 2000}],
        "largest_contentful_paint_image_time_to_first_byte": [{"p75": 500}],
    })
    assert result["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    assert result["parts_complete"] is False
    assert result["parts_sum_ms"] is None
    assert result["lcp_minus_parts_ms"] is None
