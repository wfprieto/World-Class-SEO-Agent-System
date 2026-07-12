from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from integrations.google.client import (
    GoogleAPIError,
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)
from integrations.google.crux import CrUXHistoryAdapter, decompose_lcp_history
from integrations.google.ga4 import GoogleAnalyticsDataAdapter
from integrations.google.gsc import GoogleSearchConsoleAdapter


class FakeResponse:
    def __init__(self, payload, *, status=200, headers=None):
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

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return self.responses.pop(0)


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


def test_google_json_client_retries_retryable_status_and_never_surfaces_key():
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


def test_oauth_supports_direct_token_and_rejects_unapproved_token_host():
    assert GoogleOAuthProvider(
        GoogleOAuthConfig(access_token="direct-token")
    ).token() == "direct-token"
    provider = GoogleOAuthProvider(
        GoogleOAuthConfig(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_uri="https://evil.example/token",
        )
    )
    with pytest.raises(GoogleAPIError, match="approved HTTPS Google OAuth host"):
        provider.token()


def test_gsc_query_uses_dimensionless_totals_and_paginates_rows():
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
    assert result.data["totals"] == {
        "clicks": 100.0,
        "impressions": 1000.0,
        "ctr": 0.1,
        "position": 4.2,
    }
    assert sum(row["clicks"] for row in result.data["rows"]) == 50
    assert result.data["totals_source"] == "dimensionless_aggregate_query"
    aggregate_call = client.calls[0][1]
    row_call = client.calls[1][1]
    assert "dimensions" not in aggregate_call["payload"]
    assert row_call["payload"]["dimensions"] == ["query"]
    assert token.calls == 1


def test_gsc_rejects_by_property_with_page_grouping():
    adapter = GoogleSearchConsoleAdapter(oauth=TokenProvider(), client=QueueClient([]))
    with pytest.raises(ValueError, match="byProperty"):
        adapter.query(
            "sc-domain:example.com",
            dimensions=["page"],
            aggregation_type="byProperty",
        )


def test_gsc_url_inspection_requires_url_under_property():
    adapter = GoogleSearchConsoleAdapter(oauth=TokenProvider(), client=QueueClient([]))
    with pytest.raises(ValueError, match="belong"):
        adapter.inspect("https://other.example/page", "sc-domain:example.com")

    client = QueueClient([
        {
            "inspectionResult": {
                "indexStatusResult": {
                    "verdict": "PASS",
                    "coverageState": "Submitted and indexed",
                    "googleCanonical": "https://example.com/page",
                }
            }
        }
    ])
    adapter = GoogleSearchConsoleAdapter(oauth=TokenProvider(), client=client)
    result = adapter.inspect(
        "https://www.example.com/page",
        "sc-domain:example.com",
    )
    assert result.status == "ok"
    assert result.data["verdict"] == "PASS"
    assert result.data["inspection_scope"] == "google_index_version_only"


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


def test_crux_history_bounds_periods_and_computes_latest_lcp_parts():
    periods = [
        {"firstDate": {"year": 2026, "month": 6, "day": 1}, "lastDate": {"year": 2026, "month": 6, "day": 28}}
    ]
    metrics = {
        "largest_contentful_paint": {"percentilesTimeseries": {"p75s": [2500]}},
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
    lcp = result.data["lcp_subparts"]
    assert lcp["parts_complete"] is True
    assert lcp["parts_sum_ms"] == 2400
    assert lcp["lcp_minus_parts_ms"] == 100
    assert lcp["largest_observed_part"] == {
        "name": "resource_load_duration",
        "value_ms": 800.0,
    }
    call = client.calls[0][1]
    assert call["api_key"] == "key"
    assert call["payload"]["collectionPeriodCount"] == 40

    with pytest.raises(ValueError, match="1 to 40"):
        adapter.fetch("https://example.com", collection_period_count=41)


def test_lcp_decomposition_never_estimates_missing_subparts():
    result = decompose_lcp_history({
        "largest_contentful_paint": [{"p75": 2000}],
        "largest_contentful_paint_image_time_to_first_byte": [{"p75": 500}],
    })
    assert result["parts_complete"] is False
    assert result["parts_sum_ms"] is None
    assert result["lcp_minus_parts_ms"] is None
