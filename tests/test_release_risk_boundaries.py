from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
from pathlib import Path

import pytest
import yaml

from adapters.base import AdapterNotConfigured
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from adapters.url_safety import host_is_public, validate_public_url
from integrations.authority_media.transport import BoundedTransport, TransportError
from integrations.google.client import GoogleAPIError
from integrations.technical.browser import BrowserHealth, RenderedPageService
from integrations.technical.http import BoundedHttpClient
from runtime.llm import (
    AnthropicClient,
    EchoLLMClient,
    LLMConfigurationError,
    LLMMessage,
    OpenAICompatibleClient,
    build_llm_client,
)
from scripts.validate_dependency_lock import validate as validate_dependency_lock
from scripts.validate_risk_coverage import validate


def _resolver(addresses: list[str]):
    return lambda *_args, **_kwargs: [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
        for address in addresses
    ]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/a",
        "https://user:pass@example.com/a",
        "https://example.com:8443/a",
        "https://example.com/a?access_token=secret",
        "http://127.0.0.1/a",
        "https://[::1]/a",
    ],
)
def test_url_safety_rejects_protocol_credentials_ports_secrets_and_private_ips(url: str):
    with pytest.raises(ValueError):
        validate_public_url(url, resolver=_resolver(["93.184.216.34"]))


def test_url_safety_normalizes_and_fails_closed_on_dns_anomalies():
    assert validate_public_url(
        "HTTPS://Example.COM.:443/path#fragment",
        resolver=_resolver(["93.184.216.34"]),
    ) == "https://example.com/path"
    with pytest.raises(ValueError, match="no addresses"):
        validate_public_url("https://example.com", resolver=_resolver([]))
    with pytest.raises(ValueError, match="invalid address"):
        validate_public_url("https://example.com", resolver=_resolver(["not-an-ip"]))
    with pytest.raises(ValueError, match="cannot be resolved"):
        validate_public_url(
            "https://example.com",
            resolver=lambda *_a, **_k: (_ for _ in ()).throw(socket.gaierror()),
        )
    assert host_is_public("93.184.216.34") is True
    assert host_is_public("127.0.0.1") is False
    assert host_is_public("example.com", resolver=_resolver([])) is False


class _PageSpeedClient:
    def __init__(self, crux=None):
        self.calls = []
        self.crux = crux

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        if kwargs["service"] == "crux":
            if isinstance(self.crux, Exception):
                raise self.crux
            return self.crux or {"record": {"key": {"formFactor": "PHONE"}, "metrics": {}}}
        return {
            "analysisUTCTimestamp": "2026-01-01T00:00:00Z",
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.9}},
                "audits": {"largest-contentful-paint": {"numericValue": 2100}},
                "requestedUrl": "https://example.com/",
                "finalUrl": "https://example.com/",
            },
        }


def test_pagespeed_live_adapter_exercises_credential_and_truth_state_boundaries():
    with pytest.raises(AdapterNotConfigured):
        GooglePageSpeedLiveAdapter(api_key=None, client=_PageSpeedClient()).fetch("https://example.com")
    client = _PageSpeedClient()
    result = GooglePageSpeedLiveAdapter(api_key="fixture-key", client=client).fetch(
        "https://example.com", strategy="desktop", include_crux=False
    )
    assert result.status == "ok"
    assert result.data["performance_score"] == 90
    assert result.data["crux_status"] == "skipped"
    assert client.calls[0][1]["api_key"] == "fixture-key"
    assert "fixture-key" not in str(client.calls[0][1]["query"])
    with pytest.raises(ValueError, match="strategy"):
        GooglePageSpeedLiveAdapter(api_key="x", client=client).fetch("https://example.com", strategy="tablet")
    with pytest.raises(TypeError, match="include_crux"):
        GooglePageSpeedLiveAdapter(api_key="x", client=client).fetch("https://example.com", include_crux="yes")


def test_pagespeed_live_adapter_preserves_crux_failures_without_faking_lab_failure():
    missing = _PageSpeedClient(GoogleAPIError("crux", 404, "not found"))
    result = GooglePageSpeedLiveAdapter(api_key="x", client=missing).fetch("https://example.com")
    assert result.status == "partial"
    assert result.data["crux_status"] == "not_found"
    malformed = _PageSpeedClient({"record": {"metrics": {"largest_contentful_paint": {"percentiles": {"p75": "bad"}}}}})
    result = GooglePageSpeedLiveAdapter(api_key="x", client=malformed).fetch("https://example.com")
    assert result.data["crux_status"] == "invalid_response"
    adapter = GooglePageSpeedLiveAdapter(api_key="top-secret", client=malformed)
    assert "top-secret" not in adapter._redact_secrets("failed top-secret")
    with pytest.raises(ValueError, match="approved"):
        adapter._request_json("https://example.com", params={}, api_key="x")


class _Response:
    def __init__(self, body=b"{}", *, status=200, url="https://api.example.com/data", headers=None):
        self._body = body
        self.status = status
        self.url = url
        self.headers = headers or {}
        self.closed = False

    def read(self, _size=-1):
        return self._body

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class _Opener:
    def __init__(self, *items):
        self.items = list(items)

    def open(self, *_args, **_kwargs):
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_bounded_http_transport_enforces_size_redirect_and_closure():
    response = _Response(b"ok", url="https://example.com/final", headers={"Content-Length": "2"})
    hop = BoundedHttpClient(opener=_Opener(response)).get("https://example.com/start")
    assert hop.body == b"ok" and response.closed
    oversized = _Response(b"x", url="https://example.com", headers={"Content-Length": "99"})
    with pytest.raises(ValueError, match="maximum"):
        BoundedHttpClient(max_response_bytes=2, opener=_Opener(oversized)).get("https://example.com")
    invalid = _Response(b"x", url="https://example.com", headers={"Content-Length": "invalid"})
    with pytest.raises(ValueError, match="invalid Content-Length"):
        BoundedHttpClient(opener=_Opener(invalid)).get("https://example.com")


def test_authority_transport_retries_safely_and_validates_payloads():
    sleeps = []
    opener = _Opener(TimeoutError(), _Response(b'{"ok": true}'))
    transport = BoundedTransport({"api.example.com"}, opener=opener, sleeper=sleeps.append)
    payload, response = transport.get_json("https://api.example.com/data")
    assert payload == {"ok": True} and response.status_code == 200
    assert transport.retry_count == 1 and sleeps
    with pytest.raises(ValueError, match="approved"):
        transport.get("https://evil.example/data")
    invalid = BoundedTransport({"api.example.com"}, max_attempts=1, opener=_Opener(_Response(b"not-json")))
    with pytest.raises(TransportError, match="invalid JSON"):
        invalid.get_json("https://api.example.com/data")


def test_llm_clients_cover_offline_dispatch_and_bounded_response(monkeypatch):
    echo = build_llm_client("dry-run")
    response = asyncio.run(echo.complete([LLMMessage("user", "hello")]))
    assert isinstance(echo, EchoLLMClient) and response.raw == {"dry_run": True}
    assert asyncio.run(_collect(echo.stream([LLMMessage("user", "hello")]))).strip()
    with pytest.raises(LLMConfigurationError, match="Unsupported"):
        build_llm_client("unknown")
    with pytest.raises(LLMConfigurationError, match="query"):
        OpenAICompatibleClient(api_key="x", base_url="https://api.openai.com/v1?key=x")
    with pytest.raises(LLMConfigurationError, match="ANTHROPIC_API_KEY"):
        AnthropicClient(api_key=None)

    client = OpenAICompatibleClient(api_key="x")
    monkeypatch.setattr(client, "_post_json", lambda _url, _payload: {"choices": [{"message": {"content": "ok"}}]})
    assert asyncio.run(client.complete([LLMMessage("user", "hi")])).content == "ok"


async def _collect(stream):
    return "".join([part async for part in stream])


def test_render_service_reports_renderer_failures_and_invalid_screenshots(tmp_path: Path):
    class Broken:
        def health(self):
            return BrowserHealth("installed", "installed", "fixture", "AVAILABLE", "install", "uninstall")

        def render(self, *_args, **_kwargs):
            raise RuntimeError("renderer failed")

    service = RenderedPageService(renderer=Broken())
    assert service.render("https://example.com").data["data_state"] == "FAILED"
    assert service.screenshot("https://example.com", output=tmp_path / "x.png").status == "failed"

    class Invalid(Broken):
        def render(self, *_args, **_kwargs):
            return {"screenshot_bytes": b"not-png"}

    assert RenderedPageService(renderer=Invalid()).screenshot(
        "https://example.com", output=tmp_path / "bad.png"
    ).status == "invalid_response"


def test_risk_coverage_validator_fails_missing_and_undercovered_files(tmp_path: Path):
    coverage = tmp_path / "coverage.json"
    config = tmp_path / "pyproject.toml"
    coverage.write_text(json.dumps({"files": {"runtime\\llm.py": {"summary": {"percent_covered": 79}}}}), encoding="utf-8")
    config.write_text('[tool.wcseo.risk_coverage]\n"runtime/llm.py" = 80\n"adapters/url_safety.py" = 50\n', encoding="utf-8")
    errors = validate(coverage, config)
    assert any("below required" in error for error in errors)
    assert any("missing from coverage" in error for error in errors)


def test_dependency_lock_rejects_direct_pin_outside_canonical_constraint(tmp_path: Path):
    inputs = tmp_path / "requirements-dev.in"
    lock = tmp_path / "requirements-dev.txt"
    inputs.write_text("pytest>=8,<10\n", encoding="utf-8")
    lock.write_text(
        "# This file is autogenerated by pip-compile\npytest==10.0.0\n",
        encoding="utf-8",
    )

    errors = validate_dependency_lock(inputs, lock)

    assert errors == [
        "direct requirement pin violates input constraint: pytest==10.0.0 not in <10,>=8"
    ]


def test_release_workflow_fails_closed_before_publication():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["release"]["steps"]
    names = [step.get("name", "") for step in steps]
    gate = steps[names.index("Enforce release and evidence gates")]["run"]
    publish_index = names.index("Publish immutable GitHub release assets")

    assert "validate_release_version.py --release-mode" in gate
    assert "validate_phase6_readiness.py --require-approved" in gate
    assert "inventory_comparator.py" in gate
    assert names.index("Build and verify distributions") < publish_index
    assert names.index("Attest build provenance") < publish_index
    assert names.index("Attest wheel SBOM") < publish_index
