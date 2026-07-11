"""Batch 2 integration tests (test-first).

Covers the mandated matrix: SSRF/private/metadata rejection, Playwright-unavailable
fallback, SPA detection, BOM input handling, deterministic clustering, drift
baseline/compare/schema-drift, MCP registry without credentials + secret redaction
+ no paid calls, PDF success vs HTML fallback, empty/malformed report data.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from adapters.url_safety import validate_public_url
from adapters import rendered_page
from adapters.rendered_page import RenderedPageAdapter
from adapters.page_drift import PageDrift, fingerprint
from adapters import mcp_extensions
from adapters.base import AdapterResult

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import serp_cluster  # noqa: E402
import seo_pdf_report  # noqa: E402


# --- URL safety / SSRF -------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "http://127.0.0.1/admin",              # loopback
    "http://localhost/",                   # loopback name
    "http://10.0.0.5/",                    # private
    "http://192.168.1.1/",                 # private
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
    "file:///etc/passwd",                  # non-http scheme
    "ftp://example.com/",                  # non-http scheme
    "http://user:pass@example.com/",       # credentials
    "http://example.com:8080/",            # non-standard port
])
def test_validate_public_url_rejects_hazards(bad):
    with pytest.raises(ValueError):
        validate_public_url(bad)


def test_validate_public_url_accepts_public_https():
    assert validate_public_url("https://example.com").startswith("https://example.com")


def test_rendered_page_blocks_ssrf_and_returns_adapter_result():
    result = RenderedPageAdapter().fetch(url="http://169.254.169.254/latest/meta-data/")
    assert isinstance(result, AdapterResult)
    assert result.status == "blocked"
    assert result.warnings


def test_rendered_page_has_no_duplicate_validator():
    """The adapter must reuse the canonical validator, not define its own."""
    src = Path("adapters/rendered_page.py").read_text(encoding="utf-8")
    assert "def _validate_public_url" not in src
    assert "def validate_public_url" not in src
    assert "url_safety" in src


def test_spa_detection_flags_hydration_shell():
    shell = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'
    rich = "<html><body>" + ("<p>real words here for content</p>" * 40) + "</body></html>"
    assert rendered_page.is_spa(shell) is True
    assert rendered_page.is_spa(rich) is False


def test_rendered_page_falls_back_when_playwright_unavailable(monkeypatch):
    monkeypatch.setattr(rendered_page, "_playwright_available", lambda: False)
    monkeypatch.setattr(rendered_page, "_raw_fetch", lambda u: ("<html>ok</html>", 200, {}))
    result = RenderedPageAdapter().fetch(url="https://example.com", mode="always")
    assert isinstance(result, AdapterResult)
    assert result.data["mode_used"] == "raw"
    assert result.status == "partial"
    assert any("playwright" in w.lower() for w in result.warnings)
    # Must not claim rendered/visual evidence it does not have
    assert result.data["render_engine"] is None
    assert result.data["accessibility_tree"] is None


# --- SERP clustering ---------------------------------------------------------

def _serps():
    return {
        "cheap flights": ["a", "b", "c", "d", "e"],
        "budget airfare": ["a", "b", "c", "d", "z"],
        "hotel deals": ["h1", "h2", "h3", "h4", "h5"],
    }


def test_clustering_is_deterministic():
    r1 = serp_cluster.cluster(_serps())
    r2 = serp_cluster.cluster(_serps())
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_clustering_groups_by_serp_overlap_not_text():
    res = serp_cluster.cluster(_serps())
    assert res["cluster_count"] == 2
    members = [set([c["hub"]] + c["spokes"]) for c in res["clusters"]]
    assert {"cheap flights", "budget airfare"} in members


def test_clustering_handles_empty_and_duplicate_inputs():
    assert serp_cluster.cluster({})["cluster_count"] == 0
    dup = {"a": ["u1", "u2"], "a ": ["u1", "u2"]}
    assert serp_cluster.cluster(dup)["keyword_count"] == 2


def test_clustering_handles_missing_urls():
    res = serp_cluster.cluster({"x": [], "y": []})
    assert res["cluster_count"] == 2  # no overlap => no merge


def test_serp_cluster_reads_utf8_bom(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(_serps()).encode())
    data = serp_cluster.load_json(str(p))
    assert "cheap flights" in data


# --- Page drift (over canonical EvidenceStore) -------------------------------

def test_drift_uses_canonical_evidence_store_not_a_second_db(tmp_path: Path):
    db = tmp_path / "evidence.db"
    d = PageDrift(db_path=str(db))
    d.capture("https://example.com", {"title": "A", "canonical": "https://example.com/",
                                      "robots": "index", "status_code": 200,
                                      "html": "x", "schema_json": "[1]"})
    d.close()
    # Single canonical store => the evidence table exists, no separate drift tables.
    names = {r[0] for r in sqlite3.connect(db).execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "baselines" not in names and "comparisons" not in names


def test_drift_insufficient_history_is_not_no_drift(tmp_path: Path):
    d = PageDrift(db_path=str(tmp_path / "e.db"))
    d.capture("https://example.com", {"title": "A", "status_code": 200, "html": "x"})
    res = d.compare("https://example.com")
    assert res["status"] == "insufficient_history"
    assert "counts" not in res  # must not report "no drift"
    d.close()


def test_drift_detects_unchanged_and_changed(tmp_path: Path):
    d = PageDrift(db_path=str(tmp_path / "e.db"))
    fields = {"title": "A", "canonical": "https://example.com/", "robots": "index",
              "status_code": 200, "html": "x", "schema_json": "[1]"}
    d.capture("https://example.com", fields)
    d.capture("https://example.com", dict(fields))
    same = d.compare("https://example.com")
    assert same["status"] == "ok" and same["counts"]["critical"] == 0
    assert same["changes"] == []

    changed = dict(fields, robots="noindex")
    d.capture("https://example.com", changed)
    res = d.compare("https://example.com")
    assert res["counts"]["critical"] >= 1
    assert any(c["field"] == "robots" for c in res["changes"])
    d.close()


def test_drift_detects_schema_drift_via_hash(tmp_path: Path):
    d = PageDrift(db_path=str(tmp_path / "e.db"))
    base = {"title": "A", "status_code": 200, "html": "x", "schema_json": "[1]"}
    d.capture("https://example.com", base)
    d.capture("https://example.com", dict(base, schema_json="[2]"))
    res = d.compare("https://example.com")
    assert any(c["field"] == "schema_hash" for c in res["changes"])
    d.close()


def test_fingerprint_is_deterministic_sha256():
    a = fingerprint({"title": "A", "html": "x", "schema_json": "[1]", "status_code": 200})
    b = fingerprint({"title": "A", "html": "x", "schema_json": "[1]", "status_code": 200})
    assert a == b
    assert len(a["html_hash"]) == 64


# --- MCP extension registry --------------------------------------------------

def test_mcp_registry_reports_unavailable_without_credentials(monkeypatch):
    for ext in mcp_extensions.REGISTRY.values():
        for var in ext.env_vars:
            monkeypatch.delenv(var, raising=False)
    report = mcp_extensions.capability_report(connected_mcp=set())
    assert report["available_count"] == 0
    assert all(not r["available"] for r in report["extensions"])


def test_mcp_registry_partial_configuration(monkeypatch):
    monkeypatch.setenv("AHREFS_API_KEY", "super-secret-value")
    report = mcp_extensions.capability_report(connected_mcp=set())
    ahrefs = next(r for r in report["extensions"] if r["id"] == "ahrefs")
    assert ahrefs["available"] is True


def test_mcp_registry_never_reveals_secret_values(monkeypatch):
    monkeypatch.setenv("AHREFS_API_KEY", "super-secret-value")
    blob = json.dumps(mcp_extensions.capability_report(connected_mcp=set()))
    assert "super-secret-value" not in blob


def test_mcp_registry_declares_forbidden_ops_and_no_paid_calls():
    for ext in mcp_extensions.REGISTRY.values():
        assert ext.forbidden_operations, f"{ext.id} must declare forbidden operations"
        assert ext.cost_tier in {"free", "metered"}
        if ext.cost_tier == "metered":
            assert ext.requires_cost_approval is True


def test_mcp_registry_does_not_make_network_calls():
    src = Path("adapters/mcp_extensions.py").read_text(encoding="utf-8")
    for banned in ("requests", "urlopen", "httpx", "socket.create_connection"):
        assert banned not in src


# --- PDF / HTML report -------------------------------------------------------

def _canonical_agent_output():
    return {
        "agent": "SEO Full Audit/Analyst Agent",
        "summary": "Audit summary.",
        "evidence": [{"source": "crawler_csv", "detail": "200 pages"}],
        "confidence": "Medium",
        "findings": [{"title": "Missing title", "severity": "High", "detail": "No <title>."}],
        "recommended_actions": [{"action": "Add titles", "owner": "tech"}],
        "impact": "High", "effort": "Low", "risks": ["none"], "owner": "SEO Technical Agent",
        "dependencies": [], "acceptance_criteria": ["All pages have titles"],
        "verification": "Re-crawl", "follow_up": "2026-08-01",
    }


def test_report_consumes_canonical_agent_output_and_reports_format_truthfully(tmp_path: Path):
    out = tmp_path / "r.pdf"
    res = seo_pdf_report.write_report(_canonical_agent_output(), str(out))
    # WeasyPrint is optional. The result must state exactly which artifact was produced,
    # and pdf_verified must be True only when a real PDF file exists.
    assert res.format in {"pdf", "html"}
    assert res.path.exists()
    assert res.pdf_verified == (res.format == "pdf")
    if res.format == "html":
        assert res.reason in {seo_pdf_report.DEPENDENCY_MISSING, seo_pdf_report.RENDER_FAILED}
        assert "Not Run" in res.message


def test_report_handles_empty_findings(tmp_path: Path):
    data = _canonical_agent_output()
    data["findings"] = []
    data["recommended_actions"] = []
    res = seo_pdf_report.write_report(data, str(tmp_path / "e.pdf"))
    assert res.path.exists()


def test_report_rejects_malformed_data(tmp_path: Path):
    with pytest.raises((TypeError, ValueError)):
        seo_pdf_report.write_report("not-a-dict", str(tmp_path / "m.pdf"))


def test_report_reads_utf8_bom_json(tmp_path: Path):
    p = tmp_path / "f.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(_canonical_agent_output()).encode())
    data = seo_pdf_report.load_json(str(p))
    assert data["agent"].startswith("SEO")
