"""Behavioral guards for debt extraction, without live provider traffic."""

from __future__ import annotations

import io
import urllib.error
from dataclasses import asdict
from pathlib import Path

import pytest

from adapters.ai_citation_monitor import AICitationMonitorAdapter
from adapters.backlinks import BacklinkCSVAdapter
from adapters.evidence_store import EvidenceIntegrityError, EvidenceStore, EvidenceStoreError
from adapters.ga4 import GA4ExportAdapter
from adapters.gsc import GSCExportAdapter
from adapters.hreflang_validator import HreflangValidatorAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.redirect_chain import RedirectChainAdapter
from integrations.google.client import (
    GoogleAPIError,
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)
from integrations.google.gsc import GoogleSearchConsoleAdapter
from integrations.product_proof.models import CrawlConfig, Finding, PageRecord, RobotsRecord
from runtime.workflow_graph import WorkflowGraph, WorkflowGraphError, WorkflowNode

EXPORT_ADAPTERS = [
    AICitationMonitorAdapter, BacklinkCSVAdapter, GA4ExportAdapter, GSCExportAdapter,
    HreflangValidatorAdapter, RankTrackingCSVAdapter, RedirectChainAdapter,
]


@pytest.mark.parametrize("adapter_class", EXPORT_ADAPTERS)
@pytest.mark.parametrize("adverse", [False, True])
def test_export_file_is_context_owned(monkeypatch, adapter_class, adverse):
    class Export(io.StringIO):
        def __next__(self):
            if adverse:
                raise OSError("fixture read failure")
            return super().__next__()

    stream = Export("keyword,rank\na,3\n")
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: stream)
    if adverse:
        with pytest.raises(OSError, match="fixture read failure"):
            adapter_class().fetch("fixture.csv")
    else:
        assert adapter_class().fetch("fixture.csv").source == "fixture.csv"
    assert stream.closed, "export adapters must close their files on every path"


class JsonResponse:
    status = 200

    def __init__(self, payload: bytes, declared: str | None):
        self.payload = payload
        self.headers = {} if declared is None else {"Content-Length": declared}
        self.closed = False
        self.reads = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, size):
        self.reads.append(size)
        return self.payload[:size]


class JsonOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


@pytest.mark.parametrize(
    ("payload", "declared", "message", "reads"),
    [
        (b"{}", "invalid", "invalid Content-Length", []),
        (b"{}", "12", "exceeds size limit", []),
        (b"xxxxxxxxxxxx", None, "exceeds size limit", [11]),
        (b"\xff", None, "invalid JSON", [11]),
        (b"[]", None, "not an object", [11]),
    ],
)
def test_google_json_adverse_response_closes_and_preserves_bounds(payload, declared, message, reads):
    response = JsonResponse(payload, declared)
    opener = JsonOpener(response)
    client = GoogleJsonClient(
        allowed_hosts={"www.googleapis.com"}, max_retries=2,
        max_response_bytes=10, timeout=7, opener=opener,
    )
    with pytest.raises(GoogleAPIError, match=message) as failure:
        client.request("https://www.googleapis.com/fixture", service="fixture")
    assert failure.value.state == "INVALID_RESPONSE"
    assert response.closed
    assert response.reads == reads
    assert len(opener.calls) == 1
    assert opener.calls[0][1] == 7.0
    assert client.last_telemetry == {
        "service": "fixture", "request_attempts": 1, "retry_count": 0,
        "response_status": 200, "rate_limited": False,
    }


def test_hashed_evidence_is_not_reblessed_and_closed_store_keeps_error_identity(tmp_path):
    database = tmp_path / "evidence.sqlite"
    with EvidenceStore(database) as store:
        store.record("https://EXAMPLE.com:443/a#old", "fixture", {"a/b": 1}, captured_at=1)
        store.record("https://example.com/a", "fixture", {"a/b": None}, captured_at=2)
        assert store.compare("https://example.com/a", "fixture")["drift"] == {
            "/a~1b": {"change": "changed", "before": 1, "after": None},
        }
        store._conn.execute("UPDATE snapshots SET payload_json='{}' WHERE id=1")
        store._conn.commit()
    with EvidenceStore(database) as reopened, pytest.raises(EvidenceIntegrityError, match="payload hash"):
        reopened.latest("https://example.com/a", "fixture", limit=2)
    with pytest.raises(EvidenceStoreError, match="closed"):
        reopened.latest("https://example.com/a", "fixture")


def test_graph_diagnostic_precedence_and_sorted_levels():
    duplicate = WorkflowGraph("fixture", [WorkflowNode("a", "a"), WorkflowNode("a", "b")])
    with pytest.raises(WorkflowGraphError, match="duplicate node ids"):
        duplicate.validate(max_nodes=3, max_depth=3)
    unknown = WorkflowGraph("fixture", [WorkflowNode("a", "a", ("z", "a"))], "a")
    with pytest.raises(WorkflowGraphError, match="unknown dependencies: \\['z'\\]"):
        unknown.validate(max_nodes=3, max_depth=3)
    graph = WorkflowGraph(
        "fixture", [WorkflowNode("b", "b"), WorkflowNode("a", "a"),
                    WorkflowNode("c", "c", ("b", "a"))], "c",
    )
    graph.validate(max_nodes=3, max_depth=2)
    assert [[node.id for node in level] for level in graph.levels()] == [["a", "b"], ["c"]]
    with pytest.raises(WorkflowGraphError, match="workflow depth 2 exceeds"):
        graph.validate(max_nodes=3, max_depth=1)


@pytest.mark.parametrize("kind", ["oauth", "json"])
@pytest.mark.parametrize("status", [400, 403, 429, 503])
def test_google_http_failure_closes_body_without_changing_truthful_state(kind, status):
    body = io.BytesIO(b'{"error":{"message":"fixture rejection"}}')
    failure = urllib.error.HTTPError("https://www.googleapis.com/fixture", status, "fixture", {}, body)

    class RejectingOpener:
        def open(self, request, timeout):
            raise failure

    with pytest.raises(GoogleAPIError) as captured:
        if kind == "oauth":
            GoogleOAuthProvider(
                GoogleOAuthConfig(client_id="fixture", client_secret="fixture", refresh_token="fixture"),
                opener=RejectingOpener(),
            ).token()
        else:
            GoogleJsonClient(
                allowed_hosts={"www.googleapis.com"}, opener=RejectingOpener(), max_retries=0,
            ).request("https://www.googleapis.com/fixture", service="fixture")
    expected = {400: "UNAUTHORIZED" if kind == "oauth" else "FAILED",
                403: "UNAUTHORIZED", 429: "RATE_LIMITED", 503: "FAILED"}[status]
    assert captured.value.state == expected
    assert body.closed, "rejected Google provider response must be deterministically closed"


def test_typed_finding_serialization_does_not_alias_mutable_evidence():
    finding = Finding(
        "fixture", "Fixture", "Low", "Fixture", "MISSING", "ANALYSIS", ["fixture-claim"],
        "fixture observation", "fixture impact", "fixture action", "fixture verification",
        ["https://example.com/fixture"], "fixture owner", missing_evidence=["fixture gap"],
    )
    serialized = finding.to_dict()
    serialized["claim_ids"].append("changed")
    serialized["affected_urls"].clear()
    serialized["missing_evidence"].clear()
    assert finding.claim_ids == ["fixture-claim"]
    assert finding.affected_urls == ["https://example.com/fixture"]
    assert finding.missing_evidence == ["fixture gap"]


def test_gsc_validation_order_precedes_oauth_and_filters():
    class UnusedPort:
        def token(self):
            raise AssertionError("invalid inputs must not obtain credentials")

        def request(self, *args, **kwargs):
            raise AssertionError("invalid inputs must not contact a provider")

    adapter = GoogleSearchConsoleAdapter(oauth=UnusedPort(), client=UnusedPort())
    with pytest.raises(ValueError, match="row_limit must"):
        adapter.query("sc-domain:example.com", row_limit=0, dimension_filter_groups=["invalid"])


def test_typed_serializers_preserve_every_dataclass_field_and_deep_copy():
    page = PageRecord(
        requested_url="https://example.com/", final_url="https://example.com/", depth=0,
        status_code=200, elapsed_ms=1, content_type="text/html", title="Fixture", h1=["Fixture"],
        canonical=None, meta_robots=[], x_robots_tag=None, internal_links=[], external_links=[],
        asset_urls=[], images=[{"src": "fixture.png"}], jsonld_types=[], rel_next=[], rel_prev=[],
        data_nosnippet_count=0, text_length=5, content_hash="fixture", soft_404_signal=True,
        raw_html_available=True,
    )
    robots = RobotsRecord("example.com", "https://example.com/robots.txt", 200, 1, 0, [], [], [], [])
    for record in (page, robots, CrawlConfig()):
        assert record.to_dict() == asdict(record)
    serialized = page.to_dict()
    serialized["h1"].append("changed")
    serialized["images"][0]["src"] = "changed"
    assert page.h1 == ["Fixture"]
    assert page.images == [{"src": "fixture.png"}]
