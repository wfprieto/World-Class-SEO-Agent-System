from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.mcp_extensions import (
    capability_report,
    estimate_cost,
    preflight,
    render_config,
    validate_registry,
)
from integrations.extensions.indexnow import IndexNowService, normalize
from seoctl import extensions_cli


class Response:
    status = 200
    def getcode(self): return 200
    def read(self, size): return b"secret-key-1234 accepted"


def test_registry_and_multivariable_credentials(monkeypatch):
    assert validate_registry()["status"] == "ok"
    monkeypatch.delenv("DATAFORSEO_USERNAME", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    assert "dataforseo" not in capability_report()["available"]
    monkeypatch.setenv("DATAFORSEO_USERNAME", "user-secret")
    assert "dataforseo" not in capability_report()["available"]
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "pass-secret")
    assert "dataforseo" in capability_report()["available"]


def test_templates_never_copy_secret_values(monkeypatch):
    monkeypatch.setenv("DATAFORSEO_USERNAME", "user-secret")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "pass-secret")
    rendered = json.dumps(render_config("dataforseo", "codex"))
    assert "user-secret" not in rendered
    assert "pass-secret" not in rendered
    assert "${DATAFORSEO_USERNAME}" in rendered


def test_cost_gate_and_bing_contract():
    assert estimate_cost("ahrefs", units=3)["state"] == "BLOCKED"
    approved = estimate_cost(
        "ahrefs", units=3, unit_cost=0.5, approved_ceiling=1.5, approved=True
    )
    assert approved["state"] == "APPROVED"
    assert preflight("bing-webmaster")["state"] == "BLOCKED_BY_CONTRACT"


def test_indexnow_validation_scope():
    assert normalize(["https://example.com/a", "http://example.com/b"]).host == "example.com"
    with pytest.raises(ValueError, match="one host"):
        normalize(["https://example.com/a", "https://other.example/b"])
    with pytest.raises(ValueError, match="keyLocation directory"):
        normalize(
            ["https://example.com/help/a"],
            "https://example.com/catalog/key-file.txt",
        )


def test_indexnow_default_is_blocked_and_secret_is_redacted(monkeypatch):
    monkeypatch.setenv("INDEXNOW_KEY", "secret-key-1234")
    result = IndexNowService().submit(urls=["https://example.com/a"])
    assert result.status == "blocked"
    assert "secret-key-1234" not in json.dumps(result.data)


def test_indexnow_authorized_submit_uses_post_but_redacts_key(monkeypatch):
    monkeypatch.setenv("INDEXNOW_KEY", "secret-key-1234")
    seen = {}
    def opener(request, timeout):
        seen["method"] = request.get_method()
        seen["body"] = request.data.decode()
        return Response()
    result = IndexNowService().submit(
        urls=["https://example.com/a"],
        execute=True,
        confirmation="INDEXNOW_SUBMIT",
        opener=opener,
    )
    assert result.status == "ok"
    assert seen["method"] == "POST"
    assert "secret-key-1234" in seen["body"]
    assert "secret-key-1234" not in json.dumps(result.data)
    assert result.data["response_excerpt"] == "[REDACTED] accepted"


def test_installed_wiring_is_declared():
    entrypoint = (Path(__file__).resolve().parents[1] / "seoctl" / "entrypoint.py").read_text(encoding="utf-8")
    registry = (Path(__file__).resolve().parents[1] / "adapters" / "registry.py").read_text(encoding="utf-8")
    assert "extensions_cli.main" in entrypoint
    assert "IndexNowAdapter" in registry and "ExtensionAdapter" in registry


def test_cli_routes(tmp_path: Path, monkeypatch):
    urls = tmp_path / "urls.json"
    urls.write_text(json.dumps(["https://example.com/a"]), encoding="utf-8")
    payload, code = extensions_cli.run(["indexnow", "validate", "--urls", str(urls)])
    assert code == 0 and payload["command"] == "indexnow.validate"
    payload, code = extensions_cli.run(["bing", "preflight"])
    assert code == 4 and payload["data"]["state"] == "BLOCKED_BY_CONTRACT"
    payload, code = extensions_cli.run([
        "integrations", "estimate", "--provider", "ahrefs", "--units", "2"
    ])
    assert code == 4
