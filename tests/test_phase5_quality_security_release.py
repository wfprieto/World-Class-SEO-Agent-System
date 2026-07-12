from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from adapters.base import AdapterResult
from runtime.telemetry import OperationTelemetry, redact
from runtime.tools import ToolDispatcher, ToolRequest
from scripts.generate_release_manifest import build_manifest
from scripts.generate_sbom import build_sbom
from scripts.run_performance_benchmarks import run as run_benchmarks
from scripts.run_security_mutation_checks import run as run_mutations
from scripts.scan_secrets import scan
from scripts.validate_release_artifacts import validate


class GoodAdapter:
    def fetch(self, **kwargs):
        return AdapterResult(
            source="fixture", status="ok", data={"ok": True}, warnings=[]
        )


class LeakyAdapter:
    def fetch(self, **kwargs):
        raise RuntimeError(
            "provider failed with " + "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz"
        )


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "seoctl").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="world-class-seo-agent-system"\nversion="1.7.0"\n'
        'dependencies=[\n"tenacity>=8.2.0",\n]\n',
        encoding="utf-8",
    )
    (tmp_path / "seoctl/command-registry.json").write_text(
        json.dumps({"commands": [{"id": "x"}]}), encoding="utf-8"
    )
    (tmp_path / "skills/skill-catalog.json").write_text(
        json.dumps(
            {"categories": [{"skills": [f"s{i}" for i in range(84)]}]}
        ),
        encoding="utf-8",
    )
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    return tmp_path


def test_secret_scanner_detects_real_secret_and_allows_placeholders(tmp_path: Path):
    token = "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz"
    (tmp_path / "bad.env").write_text(
        f'OPENAI_API_KEY="{token}"\n', encoding="utf-8"
    )
    assert scan(tmp_path)
    (tmp_path / "bad.env").write_text(
        'OPENAI_API_KEY="your_placeholder_key"\n', encoding="utf-8"
    )
    assert scan(tmp_path) == []


def test_telemetry_redacts_nested_secret_values():
    trace = OperationTelemetry("provider")
    trace.request_count = 1
    payload = trace.finish(
        status="OK",
        metadata={"authorization": "Bearer secret", "nested": {"api_key": "x"}},
    )
    assert payload["metadata"]["authorization"] == "[REDACTED]"
    assert payload["metadata"]["nested"]["api_key"] == "[REDACTED]"
    assert payload["duration_ms"] >= 0
    assert redact("sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz") == "[REDACTED]"


def test_dispatch_telemetry_is_present_and_error_secrets_are_sanitized():
    dispatcher = ToolDispatcher({"good": GoodAdapter(), "bad": LeakyAdapter()})
    good = asyncio.run(dispatcher.dispatch(ToolRequest("good", {})))
    assert good.status == "ok"
    bad = asyncio.run(dispatcher.dispatch(ToolRequest("bad", {})))
    assert "sk-proj" not in (bad.sanitized_error or "")
    events = dispatcher.telemetry_snapshot()
    assert events[0]["request_count"] == 1 and events[0]["status"] == "OK"
    assert events[1]["status"] == "FAILED"


def test_sbom_and_release_manifest_validate_and_detect_tampering(tmp_path: Path):
    root = _repo(tmp_path)
    sbom_payload = build_sbom(root)
    sbom = root / "sbom.json"
    sbom.write_text(json.dumps(sbom_payload), encoding="utf-8")
    manifest_payload = build_manifest(root, sbom_path=sbom)
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    assert validate(root, manifest, sbom) == []
    (root / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert any("hash mismatch" in item for item in validate(root, manifest, sbom))


def test_performance_budgets_are_bounded():
    payload = run_benchmarks(iterations=3)
    assert payload["status"] == "PASS"
    assert all(
        row["max_ms"] <= row["budget_ms"] for row in payload["results"].values()
    )


def test_secret_redaction_policy_kills_unredacted_secret_behavior():
    trace = OperationTelemetry("x")
    payload = trace.finish(status="OK", metadata={"api_key": "secret"})
    assert payload["metadata"]["api_key"] == "[REDACTED]"
    mutation = run_mutations()
    assert mutation["status"] == "PASS"
    assert mutation["killed"] == 1
