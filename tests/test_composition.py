"""Public construction contracts, characterized before migrating legacy wiring."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import socket
import ssl
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from test_tls_runtime_security import tls_certificate as tls_certificate

from runtime.llm import LLMConfigurationError, OpenAICompatibleClient
from runtime.tools import ToolDispatcher, ToolRequest
from security import url_safety
from seoctl import composition

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SHA256 = "e42fbf571fb747ebbea4b00bea25e083ace71a7a873e60a744d38b31b857f70a"


def test_default_registry_preserves_47_ordered_classes_and_distinct_aliases(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("construction must not perform network I/O")

    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    module = (
        "seoctl.composition"
        if importlib.util.find_spec("seoctl.composition") is not None
        else "adapters.registry"
    )
    adapters = importlib.import_module(module).default_adapters()
    classes = {
        key: type(value).__module__ + "." + type(value).__qualname__
        for key, value in adapters.items()
    }
    assert len(adapters) == 47
    assert len({id(value) for value in adapters.values()}) == 47
    assert (
        hashlib.sha256(json.dumps(classes, separators=(",", ":")).encode()).hexdigest()
        == REGISTRY_SHA256
    )


def test_composed_orchestrator_executes_required_default_adapter(tmp_path):
    assert importlib.util.find_spec("seoctl.composition") is not None, (
        "the public explicit composition factory is required"
    )
    composition = importlib.import_module("seoctl.composition")
    assert callable(getattr(composition, "build_orchestrator", None))
    crawl = tmp_path / "crawl.csv"
    crawl.write_text("Address,Status Code\nhttps://example.com/,200\n", encoding="utf-8")
    orchestrator = composition.build_orchestrator(ROOT)
    session = orchestrator.start_session("technical SEO audit", "audit", domain="example.com")
    result = orchestrator.execute(
        session,
        tool_requests=[ToolRequest("crawler_csv", {"path": str(crawl)}, required=True)],
        execution_mode="single-agent",
    )
    assert result["tool_results"][0]["evidence_state"] == "AVAILABLE"
    assert result["tool_results"][0]["status"] == "ok"


def test_raw_dispatcher_requires_explicit_mapping_but_empty_stays_empty():
    with pytest.raises(ValueError, match="composition"):
        ToolDispatcher()
    with pytest.raises(ValueError, match="composition"):
        ToolDispatcher(None)
    assert ToolDispatcher({}).adapters == {}


def test_live_client_requires_transport_after_configuration_checks():
    with pytest.raises(LLMConfigurationError, match="opener"):
        OpenAICompatibleClient(api_key="synthetic-fixture-key")


def test_composed_live_private_dns_is_denied_before_any_socket(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-fixture-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    client = composition.build_llm_client("openai")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    sockets = []

    def forbidden_socket(*args, **kwargs):
        sockets.append(args)
        raise AssertionError("private DNS must be denied before socket construction")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    with pytest.raises(ValueError, match="non-public"):
        client._post_json("https://api.openai.com/v1/chat/completions", {})
    assert sockets == []


@pytest.fixture
def composed_tls_site(tls_certificate, monkeypatch):
    certificate, key = tls_certificate
    observed = {"attempts": [], "sni": [], "posts": [], "auth": []}
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(str(certificate), str(key))
    server_context.set_servername_callback(
        lambda _socket, name, _context: observed["sni"].append(name)
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            observed["posts"].append(self.path)
            observed["auth"].append(
                self.headers.get("Authorization") == "Bearer synthetic-fixture-key"
            )
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path.endswith("redirect"):
                self.send_response(307)
                self.send_header("Location", "https://wrong.test/capture")
                self.end_headers()
                return
            if self.path.endswith("oversized"):
                self.send_response(200)
                self.send_header("Content-Length", "10000001")
                self.end_headers()
                return
            if self.path.endswith("retry") and observed["posts"].count(self.path) == 1:
                self.send_response(429)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b'{"choices":[{"message":{"content":"verified local TLS"}}]}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    monkeypatch.setattr(
        url_safety, "ALLOWED_TARGET_PORTS", url_safety.ALLOWED_TARGET_PORTS | {server.server_port}
    )
    connect = socket.socket.connect

    def fixture_connect(sock, address):
        if address[0] == "127.0.0.1":
            return connect(sock, address)
        observed["attempts"].append(address)
        if address == ("93.184.216.34", server.server_port):
            return connect(sock, ("127.0.0.1", server.server_port))
        raise AssertionError("composed TLS fixture refuses every unplanned destination")

    monkeypatch.setattr(socket.socket, "connect", fixture_connect)
    context = ssl.create_default_context(cafile=str(certificate))
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    monkeypatch.setattr(ssl, "_create_default_https_context", lambda: context)
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "synthetic-fixture-key")
    monkeypatch.setenv("ALLOW_CUSTOM_LLM_BASE_URL", "true")
    monkeypatch.setenv("OPENAI_BASE_URL", f"https://public.test:{server.server_port}/v1")
    monkeypatch.setenv("HTTPS_PROXY", "http://unapproved-proxy.invalid:9999")
    monkeypatch.setenv("HTTP_PROXY", "http://unapproved-proxy.invalid:9999")
    try:
        yield server.server_port, observed
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_composed_live_tls_pins_numeric_socket_preserves_identity_and_disables_proxies(
    composed_tls_site,
):
    port, observed = composed_tls_site
    client = composition.build_llm_client("openai")
    payload = client._post_json(f"https://public.test:{port}/v1/chat/completions", {})
    assert payload["choices"][0]["message"]["content"] == "verified local TLS"
    assert observed["attempts"] == [("93.184.216.34", port)]
    assert observed["sni"] == ["public.test"]
    assert observed["auth"] == [True]


def test_composed_live_redirect_does_not_forward_credentials(composed_tls_site):
    port, observed = composed_tls_site
    client = composition.build_llm_client("openai")
    with pytest.raises(LLMConfigurationError, match="redirect"):
        client._post_json(f"https://public.test:{port}/redirect", {})
    assert observed["posts"] == ["/redirect"]
    assert observed["attempts"] == [("93.184.216.34", port)]


def test_composed_live_bound_and_retry_budget(composed_tls_site):
    port, observed = composed_tls_site
    client = composition.build_llm_client("openai")
    with pytest.raises(RuntimeError, match="size limit"):
        client._post_json(f"https://public.test:{port}/oversized", {})
    assert observed["posts"] == ["/oversized"]
    assert client._post_json(f"https://public.test:{port}/retry", {})["choices"]
    assert observed["posts"] == ["/oversized", "/retry", "/retry"]


def test_composed_tls_rejects_wrong_hostname_before_credentials_are_sent(composed_tls_site):
    port, observed = composed_tls_site
    client = composition.build_llm_client("openai")
    request = urllib.request.Request(f"https://wrong.test:{port}/must-not-run", data=b"{}")
    with pytest.raises(urllib.error.URLError) as caught:
        client._opener.open(request, timeout=3)
    assert isinstance(caught.value.reason, ssl.SSLCertVerificationError)
    assert observed["posts"] == []
    assert observed["auth"] == []


def test_image_planner_propagates_exact_provider_service_and_state():
    from integrations.extensions.providers import ProviderService, image_generation_service

    class Controls:
        def preflight(self, provider_id, connected_mcp=None):
            assert provider_id == "image-gen"
            return {"state": "HOST_CLIENT_ONLY", "warnings": ["host connection required"]}

        def estimate_cost(self, provider_id, **kwargs):
            raise AssertionError("unavailable providers must not reach the cost gate")

    providers = ProviderService(Controls())
    planner = image_generation_service(providers)
    assert getattr(planner, "providers", None) is providers
    result = planner.plan(request={}, units=1, unit_cost=1, approved_ceiling=1, approved=True)
    assert result.data["state"] == "HOST_CLIENT_ONLY"
    assert result.status == "partial"


def test_raw_services_fail_truthfully_without_live_ports():
    from adapters.rendered_page import fetch
    from integrations.technical.inspection import TechnicalInspectionService

    assert fetch("https://example.com", mode="never").status == "not_configured"
    result = TechnicalInspectionService().cwv(url="https://example.com")
    assert result.status == "not_configured"
    assert result.data["live_measurement"] is False


def test_raw_orchestrator_is_offline_and_explicit_empty_is_preserved():
    from runtime.orchestrator import SEOOrchestrator

    raw = SEOOrchestrator(ROOT)
    assert raw.llm_client.provider == "echo"
    assert raw.executor.tool_dispatcher.adapters == {}
    explicit = ToolDispatcher({})
    composed = composition.build_orchestrator(ROOT, tool_dispatcher=explicit)
    assert composed.executor.tool_dispatcher is explicit


def test_product_proof_composition_passes_explicit_canonical_asset_path():
    service = composition.build_product_proof_service(ROOT)
    assert service.claim_registry == ROOT / "knowledge" / "seo-claim-registry.json"


def test_injected_drift_factory_closes_and_keeps_canonical_hashes(tmp_path):
    from adapters.evidence_store import canonicalize_url
    from adapters.page_drift import PageDrift, fingerprint
    from integrations.authority_media.drift import DriftService

    opened = []
    identities = []

    @contextmanager
    def factory(db_path):
        with PageDrift(db_path) as drift:
            opened.append(drift)
            yield drift

    def identity(url):
        identities.append(url)
        return canonicalize_url(url)

    state = {"title": "Stable", "html": "original", "schema_json": "[1]", "status_code": 200}
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    database = str(tmp_path / "evidence.db")
    service = DriftService(factory, identity)
    baseline = service.baseline("https://EXAMPLE.com", str(path), db_path=database)
    assert baseline.data["url"] == canonicalize_url("https://EXAMPLE.com")
    assert identities == ["https://EXAMPLE.com"]
    assert opened[0]._store._closed is True
    with PageDrift(database) as drift:
        history = drift.history("https://example.com/")
        assert history[0]["payload"] == fingerprint(state)
    assert service.compare("https://example.com/", db_path=database).status == "partial"
    assert all(drift._store._closed for drift in opened)


def test_entity_entrypoints_keep_the_exact_provider_service():
    from integrations.content_intelligence.service import ContentIntelligenceService
    from integrations.extensions.providers import ProviderService, normalize_entity_analysis

    calls = []

    class Controls:
        def preflight(self, provider_id, connected_mcp=None):
            calls.append(provider_id)
            return {"state": "AVAILABLE", "warnings": []}

    providers = ProviderService(Controls())
    service = ContentIntelligenceService(providers)
    assert service.providers is providers
    payload = {
        "provider": "entity-analysis", "captured_at": "2026-10-29T12:00:00Z",
        "source": "synthetic-provider-receipt", "entities": [],
        "cost_approval": {"state": "APPROVED", "estimated_cost": 0.0, "approved_ceiling": 0.0},
    }
    normalized = normalize_entity_analysis(payload, providers=providers)
    result = service.entities(text="Example is supplied text.", provider_analysis=payload)
    assert result.data["provider_analysis"] == normalized
    assert calls == ["entity-analysis", "entity-analysis"]


def test_commoncrawl_injected_identity_and_live_transport_keep_pagination_contract():
    from adapters.evidence_store import canonicalize_url
    from integrations.authority_media.services import CommonCrawlService

    class Transport:
        request_count = 3
        retry_count = 0

        def __init__(self):
            self.urls = []

        def get_json(self, url):
            self.urls.append(url)
            return [{"id": "controlled-index", "cdx-api": "https://index.commoncrawl.org/controlled-index"}], None

        def get_text(self, url):
            self.urls.append(url)
            page = len(self.urls) - 2
            return json.dumps({"url": f"https://EXAMPLE.com/page-{page}", "status": "200"}), None

    transport = Transport()
    service = CommonCrawlService(canonicalize_url, transport=transport)
    result = service.search("example.com", max_pages=2, page_size=1)
    assert result.status == "ok"
    assert result.data["record_count"] == 2
    assert result.data["request_count"] == 3
    assert result.data["retry_count"] == 0
    assert [row["url"] for row in result.data["records"]] == [
        "https://example.com/page-0", "https://example.com/page-1",
    ]
    assert len(transport.urls) == 3
    assert transport.urls[1].endswith("pageSize=1&page=0")
    assert transport.urls[2].endswith("pageSize=1&page=1")
