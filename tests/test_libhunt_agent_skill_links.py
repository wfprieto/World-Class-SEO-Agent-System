from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_PACK = "knowledge/reference-packs/framework-seo-implementation-expanded.md"


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_phase_7_agents_have_framework_pack_capability_links():
    capability = _json("orchestration/capability-registry.json")
    expected_agents = {
        "Senior SEO Engineer Agent",
        "SEO Technical Agent",
        "International & Multilingual SEO Agent",
        "Visual & Video Search Agent",
    }
    for agent in expected_agents:
        assert FRAMEWORK_PACK in capability["agents"][agent]["knowledge_files"], agent


def test_unrelated_agents_do_not_receive_framework_pack_by_default():
    capability = _json("orchestration/capability-registry.json")
    unrelated = {
        "SEO Accessibility Agent",
        "SEO CRO Agent",
        "SEO Information Architecture Agent",
    }
    for agent in unrelated:
        assert FRAMEWORK_PACK not in capability["agents"][agent]["knowledge_files"], agent


def test_docs_surface_libhunt_and_framework_links():
    skills_doc = (ROOT / "docs" / "SKILLS-REFERENCES-PROMPTS.md").read_text(encoding="utf-8")
    integration_doc = (ROOT / "docs" / "INTEGRATION-MANIFEST.md").read_text(encoding="utf-8")
    assert "evaluation/libhunt-source-ingestion-matrix.json" in skills_doc
    assert FRAMEWORK_PACK in skills_doc
    assert "LibHunt clean-room source governance" in integration_doc
    assert FRAMEWORK_PACK in integration_doc
