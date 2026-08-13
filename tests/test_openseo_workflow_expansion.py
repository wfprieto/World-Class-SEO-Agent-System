from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_find_flow_has_cost_aware_keyword_tool_plan():
    body = _read("skills/flow-prompts/find.md")
    assert "cost-aware-keyword-tool-plan" in body
    assert "Free-first path" in body
    assert "Cost and quota risk" in body
    assert "tool_plan" in body


def test_leverage_flow_has_cost_aware_link_prospecting_plan():
    body = _read("skills/flow-prompts/leverage.md")
    assert "cost-aware-link-prospecting-plan" in body
    assert "Relevance filter" in body
    assert "Risk filter" in body
    assert "undisclosed sponsorship" in body


def test_optimize_flow_has_tool_evidence_merge():
    body = _read("skills/flow-prompts/optimize.md")
    assert "tool-evidence-merge" in body
    assert "first-party observed" in body
    assert "third-party estimated" in body
    assert "URL normalization and date windows" in body


def test_openseo_adaptation_doc_is_clean_room_and_guardrailed():
    body = _read("docs/OPENSEO-WORKFLOW-ADAPTATION.md")
    assert "clean-room" in body
    assert "No paid tool is required" in body
    assert "No third-party metric is treated as exact ground truth" in body
