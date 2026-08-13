from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate as validate_references


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "knowledge" / "reference-packs" / "framework-seo-implementation-expanded.md"


def test_framework_notes_cover_required_phase_7_topics():
    body = PACK.read_text(encoding="utf-8").lower()
    for phrase in (
        "next.js app router",
        "metadata generation",
        "json-ld",
        "dynamic sitemap",
        "robots.txt",
        "sitemap indexes",
        "image, video, news",
        "hreflang alternates",
        "canonical",
        "rendered output",
    ):
        assert phrase in body


def test_framework_notes_are_advisory_not_universal_policy():
    body = PACK.read_text(encoding="utf-8").lower()
    assert "advisory until mapped to the target stack" in body
    assert "validate the rendered output" in body
    assert "do not assume a framework package fixes" in body
    assert "not proof of eligibility" in body


def test_framework_pack_registry_links_phase_7_agents_and_skills():
    assert validate_references() == []
    registry = json.loads((ROOT / "knowledge" / "reference-registry.json").read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in registry["entries"]
        if entry["pack"] == "framework-seo-implementation-expanded"
    ]
    agents = {agent for entry in entries for agent in entry["affected_agents"]}
    skills = {skill for entry in entries for skill in entry["affected_skills"]}
    assert "Senior SEO Engineer Agent" in agents
    assert "SEO Technical Agent" in agents
    assert "International & Multilingual SEO Agent" in agents
    assert "Visual & Video Search Agent" in agents
    assert "technical-implementation" in skills
    assert "sitemap-audit" in skills
    assert "hreflang-audit" in skills
