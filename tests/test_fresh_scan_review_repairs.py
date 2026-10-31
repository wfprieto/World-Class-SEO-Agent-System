"""Regression controls for confirmed independent candidate-review findings."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from test_fresh_scan_brief_integrity import producer_assessments

from adapters import rendered_page
from scripts.seo_pdf_report import build_html
from scripts.workflow_quality_contract import _jobs, workflow_errors
from seoctl import cli
from seoctl.composition import build_content_service

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["validate.yml", "maintenance.yml"])
def test_normal_ci_pytest_cannot_leave_executable_rewrite_caches(name, tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
    commands = [step["run"].strip() for job in workflow["jobs"].values()
                for step in job.get("steps", []) if "pytest " in step.get("run", "")]
    assert commands and all(re.match(r"python -B -m pytest(?:\s|$)", command) for command in commands)
    fixture = tmp_path / "test_fixture.py"
    fixture.write_text("def test_fixture():\n    assert 1 == 1\n", encoding="utf-8")
    environment = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(fixture)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(tmp_path.rglob("*.pyc"))


@pytest.mark.parametrize("mode", ["auto", "always", "never"])
def test_bounded_spa_analysis_preserves_raw_fallback_and_render_modes(monkeypatch, mode):
    raw = '<div id="root"><img src="data:image/png;base64,' + "A" * 70_000 + '"></div>'
    calls = []
    monkeypatch.setattr(rendered_page, "validate_public_url", lambda value: value)
    monkeypatch.setattr(rendered_page, "_raw_fetch", lambda _url: (raw, 200, {}))

    def render(_url, _block):
        calls.append(True)
        return {"content": "<main>Rendered fixture</main>", "render_engine": "injected-fixture"}

    result = rendered_page.fetch("https://example.com/", mode=mode, render_fn=render, raw_fetch=rendered_page._raw_fetch)
    assert result.data["raw_content"] == raw
    assert result.data["is_spa"] is None
    assert any(warning.startswith("analysis_failed:") for warning in result.warnings)
    assert len(calls) == (1 if mode == "always" else 0)
    assert result.status == ("ok" if mode == "always" else "partial")
    assert result.data["evidence"]["rendered"] == ("Verified" if mode == "always" else "Not Run")


@pytest.mark.parametrize("invalid_gain", [None, {}, False])
def test_brief_cli_must_not_stringify_malformed_information_gain(monkeypatch, invalid_gain):
    relevance, serp = producer_assessments()
    packets = {"relevance": relevance, "serp": serp, "gains": [invalid_gain]}
    monkeypatch.setattr(cli, "_json", packets.__getitem__)
    args = SimpleNamespace(relevance="relevance", serp="serp", information_gain="gains",
                           conditions_resolved=False, selected_intent=None)
    result, code = cli._content_brief_decision(args)
    assert code == cli.EXIT_BLOCKED
    assert result["data"]["publish"] is False


@pytest.mark.parametrize("invalid_gain", [None, {}, False])
def test_brief_service_must_not_stringify_malformed_information_gain(invalid_gain):
    relevance, serp = producer_assessments()
    result = build_content_service().brief(
        relevance=relevance, serp=serp, information_gains=[invalid_gain],
        sources=[{"id": "fixture-source", "title": "Supplied source"}],
        audience="Facility managers", intent="informational", primary_question="What evidence?",
        required_sections=["Evidence"],
    )
    assert result.status == "blocked"


@pytest.mark.parametrize("suffix", ["--junitxml=pytest-results.xml", "--cov=runtime"])
def test_finite_ci_contract_rejects_removing_no_bytecode_flag(suffix):
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    selected = "python -B -m pytest -q --browser-security " + suffix
    assert selected in workflow
    changed = workflow.replace(selected, selected.replace("python -B -m", "python -m"), 1)
    release = (ROOT / ".github/workflows/release.yml").read_text()
    assert workflow_errors(changed, 78, release)


def test_report_markup_includes_a_meaningful_document_title():
    markup = build_html({"agent": "QA fixture", "summary": "Synthetic report", "findings": []})
    assert "<title>SEO Report</title>" in markup


def test_ci_exact_no_write_policy_is_allowed_at_global_scope():
    payload = {"env": {"PYTHONDONTWRITEBYTECODE": "1"}, "jobs": {}}
    assert _jobs(yaml.safe_dump(payload))[1] == []
