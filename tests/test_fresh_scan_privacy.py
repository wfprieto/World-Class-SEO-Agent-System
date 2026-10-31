"""Synthetic regressions for privacy boundaries identified by the fresh-main scan."""

from __future__ import annotations

import hashlib
import html
import json
import socket
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from adapters.evidence_store import EvidenceStore
from adapters.rendered_evidence import blank_evidence
from integrations.extensions.indexnow import IndexNowService, normalize
from integrations.product_proof.adapters import ProductProofIntelligenceAdapter
from integrations.product_proof.intelligence import AITimeoutAnalyzer
from integrations.product_proof.service import ProductProofTechnicalAudit
from integrations.technical.http import BoundedHttpClient, HttpHop
from runtime.llm import LLMResponse
from runtime.memory import JsonlMemoryStore
from runtime.public_results import public_result_mapping
from runtime.schema_registry import SchemaRegistry
from runtime.tools import ToolDispatcher, ToolRequest
from runtime.workflow_graph import WorkflowGraph, WorkflowNode
from scripts.consent_mode_diagnostic import SIGNALS, diagnose
from security.url_safety import validate_public_url
from sensitive_data import redact
from seoctl.cli import envelope
from seoctl.composition import build_orchestrator as SEOOrchestrator


def test_embedded_url_secrets_are_removed_before_persistence(tmp_path):
    markers = ("dummy-code-value", "dummy-key-value", "dummy-id-value", "dummy-user-value")
    content = (
        '<a href="https://dummy-user-value:dummy-pass@example.com/?code=dummy-code-value'
        '&amp;%6bey=dummy-key-value&amp;idToken=dummy-id-value&page=2">safe</a>'
    )
    evidence = blank_evidence("https://example.com/", content, 200, {}, is_spa=False)
    memory = JsonlMemoryStore(tmp_path / "memory.jsonl")
    memory.append("fixture-session", {"content": content})
    db_path = tmp_path / "evidence.db"
    with EvidenceStore(db_path) as store:
        store.record("https://example.com/", "privacy", {"content": content},
                     source=content, run_id="fixture-run", scope={"detail": content})
        record = store.latest("https://example.com/", "privacy")[0]
    exported = json.dumps(evidence) + json.dumps(record) + memory.path.read_text(encoding="utf-8")
    assert all(marker not in exported for marker in markers)
    assert all(marker.encode() not in db_path.read_bytes() for marker in markers)
    assert "page=2" in exported and "safe" in exported
    assert record["run_id"] == "fixture-run"


class _PrivacyHrefParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.href = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href", "")


@pytest.mark.parametrize("sink", ["rendered", "jsonl", "sqlite", "consent", "public"])
@pytest.mark.parametrize("encoded,credential", [
    ("&#100;ummy-entity-secret", "dummy-entity-secret"),
    ("&#x64;ummy-entity-secret", "dummy-entity-secret"),
    ("&#X00064;ummy-entity-secret", "dummy-entity-secret"),
    ("&#100ummy-entity-secret", "dummy-entity-secret"),
    ("&sol;dummy-entity-secret", "/dummy-entity-secret"),
    ("prefix&sol;dummy-entity-secret", "prefix/dummy-entity-secret"),
    ("&num;dummy-entity-secret", "#dummy-entity-secret"),
    ("&amp;#100;ummy-entity-secret", "dummy-entity-secret"),
    ("&#38;#x64;ummy-entity-secret", "dummy-entity-secret"),
    ("&amp;amp;#100;ummy-entity-secret", "dummy-entity-secret"),
    ("&amp;sol;dummy-entity-secret", "/dummy-entity-secret"),
    ("&copydummy-entity-secret", "\u00a9dummy-entity-secret"),
    ("&amp;copydummy-entity-secret", "\u00a9dummy-entity-secret"),
    ("".join(f"&#{ord(char)};" for char in "opaque-entity-credential"), "opaque-entity-credential"),
])
def test_entity_encoded_query_values_are_removed_across_privacy_sinks(tmp_path, sink, encoded, credential):
    content = f'<a href="https://example.com/?code={encoded}&amp;page=2">&lt;safe&gt;</a>'
    supplied = {"content": content, "deployment": "preview"}
    original = json.dumps(supplied)
    if sink == "rendered":
        exported = blank_evidence("https://example.com/", content, 200, {}, is_spa=False)
        projected = exported["content"]
    elif sink == "jsonl":
        memory = JsonlMemoryStore(tmp_path / "entity-memory.jsonl")
        memory.append("entity-fixture", supplied)
        exported = memory.load("entity-fixture")[0]
        projected = exported["content"]
        exported = {"loaded": exported, "bytes": memory.path.read_text(encoding="utf-8")}
    elif sink == "sqlite":
        with EvidenceStore(tmp_path / "entity-evidence.db") as store:
            store.record("https://example.com/", "privacy", supplied,
                         source=content, scope={"detail": content}, run_id="entity-fixture")
            exported = store.latest("https://example.com/", "privacy")[0]
        projected = exported["payload"]["content"]
        assert exported["run_id"] == "entity-fixture"
    elif sink == "consent":
        exported = diagnose({"cmp": True, "region": "US-CA", "environment": supplied})
        projected = exported["implementation_topology"]["environment"]["content"]
        assert exported["implementation_topology"]["environment"]["deployment"] == "preview"
    else:
        exported = public_result_mapping(supplied)
        projected = exported["content"]
    decoded = json.dumps(exported)
    parser = _PrivacyHrefParser()
    parser.feed(projected)
    href = parser.href
    for _ in range(8):
        decoded = html.unescape(decoded)
        href = html.unescape(href)
    assert credential not in decoded
    query = parse_qs(urlsplit(href).query, keep_blank_values=True)
    assert query == {"code": ["[REDACTED]"], "page": ["2"]}
    assert projected.endswith('">&lt;safe&gt;</a>')
    assert json.dumps(supplied) == original


def test_entity_value_redaction_does_not_rescan_consumed_encoded_values():
    code = (
        "from sensitive_data import redact; "
        "value = '<a href=\"https://example.com/?code=' + '&sol;' * 12000 + '\">safe</a>'; "
        "assert redact(value) == '<a href=\"https://example.com/?code=[REDACTED]\">safe</a>'"
    )
    try:
        completed = subprocess.run([sys.executable, "-B", "-c", code],
                                   cwd=Path(__file__).resolve().parents[1],
                                   capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired:
        pytest.fail("redaction rescanned a consumed entity value beyond the controlled CPU bound")
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("separator", ["&", "&amp;", "&#38;"])
@pytest.mark.parametrize("name", ["copy", "not", "amp"])
def test_entity_named_query_fields_remain_distinct_from_credential_values(separator, name):
    value = f"https://example.com/?code=opaque-private-value{separator}{name}=2&page=3"
    assert redact(value) == f"https://example.com/?code=[REDACTED]{separator}{name}=2&page=3"


def test_public_workflow_results_redact_echoes_without_destroying_session_schema(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    graph = WorkflowGraph(
        id="privacy-fixture", nodes=[WorkflowNode(id="report", agent="SEO Output Report Agent")],
        deliverable_node_id="report",
    )
    monkeypatch.setattr("runtime.workflow_runner.build_workflow_graph", lambda *_: graph)
    orchestrator = SEOOrchestrator(root)
    session = orchestrator.start_session(
        request="Audit example.com password=dummy-request-secret", mode="Audit", domain="example.com"
    )
    result = orchestrator.execute(session, orchestrator.route(session))
    payload = envelope("system.run", "partial", result)
    assert "dummy-request-secret" not in json.dumps(payload)
    exported_session = payload["data"]["session"]
    SchemaRegistry(root).validate("session-state", exported_session)
    assert exported_session["session_id"] == session.session_id
    assert payload["data"]["agent_output"]["output_id"] == session.agent_outputs[-1]["output_id"]
    assert exported_session["workflow_events"][0]["event_id"].startswith(session.session_id)
    assert "dummy-request-secret" in session.request  # operational state is not mutated
    untrusted = envelope("fixture", "ok", {"tool": {"session": "private-session", "session_id": "private-client"}})
    assert untrusted["data"]["tool"] == {"session": "[REDACTED]", "session_id": "[REDACTED]"}


def test_indexnow_rejects_credential_urls_before_preview_or_submission(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("privacy normalization must not resolve or transmit")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    service = IndexNowService()
    for alias in ("token", "%61ccess_token", "apiKey", "idToken", "SESSIONID", "client-secret"):
        unsafe = f"https://example.com/?{alias}=dummy-indexnow-secret"
        for urls, location in (([unsafe], None), (["https://example.com/"], unsafe)):
            with pytest.raises(ValueError, match="credential"):
                service.validate(urls=urls, key_location=location)
            with pytest.raises(ValueError, match="credential"):
                service.submit(urls=urls, key_location=location, key="dummy-key", opener=forbidden)
            with pytest.raises(ValueError, match="credential"):
                service.submit(urls=urls, key_location=location, key="dummy-key", execute=True,
                               confirmation="INDEXNOW_SUBMIT", opener=forbidden)
    benign = "https://example.com/catalog?page=2&utm_campaign=fall"
    assert normalize([benign]).urls == (benign,)
    assert service.validate(urls=[benign]).data["urls"] == [benign]


def test_crawl_projects_all_artifacts_and_metadata_before_manifest_hashing(tmp_path):
    root = Path(__file__).resolve().parents[1]
    target = "https://example.com/?token=dummy-target-secret&page=2"
    fixture = tmp_path / "crawl-fixture.json"
    fixture.write_text(json.dumps({"responses": {
        target: {"headers": {"Content-Type": "text/html"}, "body": '''
            <html><head><title>Page</title>
            <link rel="canonical" href="https://example.com/?code=dummy-canonical-secret">
            <link rel="next" href="/?page=3&amp;apiKey=dummy-next-secret">
            <link rel="stylesheet" href="https://cdn.example.com/?key=dummy-asset-secret">
            </head><body><h1>Page</h1><p>Substantial ordinary content for this fixture page.</p>
            <a href="https://dummy-user-secret:dummy-pass@example.net/path">external</a>
            <a href="/?password=dummy-link-secret">internal</a>
            <img src="https://cdn.example.com/?idToken=dummy-image-secret" alt="fixture">
            </body></html>'''},
        "https://example.com/robots.txt": {"body": "User-agent: *\nSitemap: https://example.com/?key=dummy-robots-secret\n"},
        "https://cdn.example.com/robots.txt": {"status_code": 404, "body": ""},
    }}), encoding="utf-8")
    output = tmp_path / "artifacts"
    result = ProductProofTechnicalAudit(claim_registry=root / "knowledge/seo-claim-registry.json").run(
        url=target, output_dir=output, fixture_path=fixture, max_urls=5, max_depth=1,
    )
    artifact_text = "\n".join(path.read_text(encoding="utf-8") for path in output.iterdir())
    assert "dummy-" not in artifact_text + json.dumps(result.data)
    crawl = json.loads((output / "crawl.json").read_text(encoding="utf-8"))
    assert "page=2" in crawl["start_url"] and "page=3" in crawl["pages"][0]["rel_next"][0]
    assert crawl["failed_fetches"] and result.data["run_id"]
    manifest = json.loads((output / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == result.data["run_id"]
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256(Path(manifest["artifacts"][name]).read_bytes()).hexdigest() == digest


def test_consent_redacts_aliases_and_text_without_losing_nested_matrix_metadata():
    metadata = {"deployment": "preview", "metadata": [{
        "accessToken": "dummy-consent-access", "tcString": "dummy-consent-tc",
        "clientId": "dummy-consent-client", "userId": "dummy-consent-user",
        "session_id": "dummy-consent-session", "credential": "dummy-consent-credential",
        "notes": "Bearer dummy-consent-bearer https://example.com/?code=dummy-consent-url&page=2",
    }]}
    config = {"cmp": "fixture-cmp", "region": "US-CA", "mode": "advanced",
              "defaults": dict.fromkeys(SIGNALS, "denied"), "default_set": True,
              "default_before_tags": True, "environment": metadata, "extra": metadata}
    for changes in ({}, {"cmp": False}, {"mode": "invalid"}, {"defaults": {"ad_storage": "dummy-invalid-state"}}):
        report = diagnose(config | changes)
        assert "dummy-" not in json.dumps(report)
        env = report["implementation_topology"]["environment"]
        assert env["deployment"] == "preview" and isinstance(env["metadata"], list)
        assert "page=2" in env["metadata"][0]["notes"]
        assert set(report["consent_state_matrix"]) == set(SIGNALS)
        assert all(row["treated_as"] == "denied" for row in report["consent_state_matrix"].values())
        assert report["region_resolution"]["requested_region"] == "US-CA"
        assert "No consent strings, identifiers, or user data are retained" not in json.dumps(report)


@pytest.mark.parametrize("alias", ["USERID", "user.id", "uSeR_iD"])
def test_consent_identifier_alias_case_and_separators_are_equivalent(alias):
    report = diagnose({"cmp": True, "region": "US", "environment": {alias: "dummy-user-alias", "user_role": "operator"}})
    assert "dummy-user-alias" not in json.dumps(report)
    assert report["implementation_topology"]["environment"]["user_role"] == "operator"


def test_public_projection_preserves_only_known_credential_transport_metadata():
    metadata = envelope("google.pagespeed", "ok", {"credential_transport": "X-Goog-Api-Key header"})
    assert metadata["data"]["credential_transport"] == "X-Goog-Api-Key header"
    secret = envelope("fixture", "ok", {"credential_transport": "dummy-secret-transport"})
    assert "dummy-secret-transport" not in json.dumps(secret)


def test_access_log_targets_are_sanitized_before_aggregation(tmp_path):
    log = tmp_path / "access.log"
    targets = [
        "/reset?token=dummy-log-token&page=1", "/reset?token=dummy-log-other&page=1",
        "/reset?apiKey=dummy-log-key&page=2",
        "https://dummy-log-user:dummy-log-pass@example.com/?code=dummy-log-code&page=3",
    ]
    log.write_text("\n".join(
        f'203.0.113.2 - - [30/Oct/2026:10:00:00 -0400] "GET {target} HTTP/1.1" '
        f'{499 if index != 2 else 200} 0 "-" "ChatGPT-User/1.0" request_time=0.1'
        for index, target in enumerate(targets)
    ), encoding="utf-8")
    report = AITimeoutAnalyzer().analyze(log_path=log, server_stack="nginx")
    assert "dummy-" not in json.dumps(report.data)
    assert report.data["ai_requests"] == 4 and report.data["timeout_499_count"] == 3
    assert report.data["top_paths"][0]["count"] == 2
    assert len(report.data["top_paths"]) == 3
    assert {row["path"].split("page=")[-1] for row in report.data["top_paths"]} == {"1", "2", "3"}


def test_redirect_evidence_excludes_raw_headers_and_blocked_credential_target(monkeypatch):
    hop = HttpHop(
        requested_url="https://example.com/?page=2", final_url="https://example.com/?page=2",
        status_code=302, headers={"Content-Type": "text/html", "Set-Cookie": "sid=dummy-cookie-secret",
                                  "Authorization": "Bearer dummy-header-secret", "X-Private": "dummy-private-secret",
                                  "Location": "/reset?token=dummy-redirect-secret"},
        body=b"", elapsed_ms=7,
    )
    exported = hop.as_dict()
    assert "dummy-" not in json.dumps(exported)
    assert exported["headers"] == {"content-type": "text/html"}
    assert exported["status_code"] == 302 and exported["elapsed_ms"] == 7
    assert hop.headers["Location"] == "/reset?token=dummy-redirect-secret"
    client = BoundedHttpClient()
    monkeypatch.setattr(client, "_single_request", lambda _: hop)
    chain = client.redirect_chain("https://example.com/?page=2")
    assert chain["data_state"] == "BLOCKED" and chain["hop_count"] == 1
    assert "dummy-" not in json.dumps(chain)
    assert chain["blocked_target"] == "https://example.com/reset"


def test_canonical_outbound_url_query_aliases_are_rejected():
    for alias in ("idToken", "client-secret", "%2561ccess_token", "page=1&amp;sessionId"):
        with pytest.raises(ValueError, match="credential"):
            validate_public_url(f"https://example.com/?{alias}=dummy-canonical-secret")
    benign = "https://example.com/?page=2&color=green"
    assert validate_public_url(benign) == benign


@pytest.mark.parametrize("text", [
    '{"password": "dummy-quoted-secret with spaces"}',
    "apiKey: 'dummy-quoted-secret'", "session_id=dummy-quoted-secret",
    "idToken=dummy-quoted-secret", "clientId=dummy-quoted-secret",
])
def test_canonical_labeled_secret_forms_are_redacted(text):
    assert "dummy-quoted-secret" not in str(redact(text))
    if text.startswith("{"):
        assert json.loads(redact(text)) == {"password": "[REDACTED]"}
    assert redact("ordinary context page=2") == "ordinary context page=2"


def test_html_entity_encoded_url_credentials_are_removed_without_decoding_markup():
    text = ('<a href="https://dummy-entity-user:dummy-entity-pass&#64;example.com/'
            '?access&#95;token=dummy-entity-token&amp;api&#75;ey=dummy-entity-api&amp;page=2">&lt;safe&gt;</a>')
    result = redact(text)
    assert "dummy-entity-" not in result
    assert "page=2" in result and "&lt;safe&gt;" in result
    assert redact("https://example.com/#section@ordinary") == "https://example.com/#section@ordinary"


@pytest.mark.parametrize("separator", ["&#38;", "&#x26;", "&AMP;"])
def test_html_entity_query_separators_cannot_hide_encoded_secret_names(separator):
    result = redact(f"https://example.com/?page=2{separator}%6bey=dummy-separator-secret")
    assert "dummy-separator-secret" not in result and "page=2" in result


def test_credential_urls_used_as_mapping_keys_do_not_leak_or_drop_entries(tmp_path):
    safe_key = "https://example.com/?code=[REDACTED]&page=2"
    original = {"https://example.com/?code=dummy-key-first&page=2": "first",
                "https://example.com/?code=dummy-key-second&page=2": "second", safe_key: "safe"}
    memory = JsonlMemoryStore(tmp_path / "key-memory.jsonl")
    memory.append("fixture", original)
    consent_environment = diagnose({"cmp": True, "region": "US", "environment": original})["implementation_topology"]["environment"]
    for projected in (redact(original), public_result_mapping(original), memory.load("fixture")[0], consent_environment):
        assert "dummy-key-" not in json.dumps(projected)
        assert len(projected) == 3 and set(projected.values()) == {"first", "second", "safe"}
        assert projected[safe_key] == "safe"
        assert all("page=2" in key for key in projected)


@pytest.mark.parametrize("execution_mode", ["single-agent", "multi-agent"])
def test_registered_log_adapter_never_sends_query_credentials_to_model(tmp_path, monkeypatch, execution_mode):
    captured = []

    class CapturingModel:
        provider = "privacy-fixture"
        model = "synthetic-capture"

        async def complete(self, messages):
            captured.extend(message.content for message in messages)
            context = json.loads(next(message.content for message in messages if message.role == "user").split("\n\n", 1)[1])
            agent = context["agent"]
            output = {
                "contract_version": "2.0.0", "output_id": "fixture-log-output", "agent": agent,
                "summary": "Supplied log requires operator review.", "evidence": [], "confidence": "Low",
                "findings": [], "recommended_actions": [], "impact": "Fixture-only diagnostic review.",
                "effort": "Low", "risks": [], "owner": agent, "dependencies": [],
                "acceptance_criteria": [], "verification": [], "follow_up": "Before implementation.",
                "material_claims": [], "execution_state": "COMPLETE",
            }
            return LLMResponse(self.provider, self.model, json.dumps(output), {"fixture": True})

        async def stream(self, messages):
            yield (await self.complete(messages)).content

    log = tmp_path / "model-log.txt"
    log.write_text('203.0.113.2 - - [30/Oct/2026:10:00:00 -0400] '
                   '"GET /reset?idToken=dummy-model-secret&page=2 HTTP/1.1" 499 0 "-" "ChatGPT-User/1.0"\n', encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    graph = WorkflowGraph(id="privacy-model", nodes=[WorkflowNode(id="report", agent="SEO Output Report Agent")], deliverable_node_id="report")
    monkeypatch.setattr("runtime.workflow_runner.build_workflow_graph", lambda *_: graph)
    dispatcher = ToolDispatcher(adapters={"product_proof_intelligence": ProductProofIntelligenceAdapter()})
    orchestrator = SEOOrchestrator(root, llm_client=CapturingModel(), tool_dispatcher=dispatcher)
    session = orchestrator.start_session("Prepare a client report.", "Audit", domain="example.com")
    result = orchestrator.execute(session, orchestrator.route(session), [ToolRequest(
        "product_proof_intelligence", {"operation": "ai_timeouts", "log_path": str(log), "server_stack": "nginx"}, required=True,
    )], execution_mode=execution_mode)
    assert captured and "dummy-model-secret" not in "\n".join(captured)
    assert "page=2" in "\n".join(captured)
    assert result["tool_results"][0]["data"]["ai_requests"] == 1
    assert result["tool_results"][0]["data"]["timeout_499_count"] == 1
    assert result["agent_output"]["output_id"] == "fixture-log-output"
