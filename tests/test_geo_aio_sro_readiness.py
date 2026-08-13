from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate


ROOT = Path(__file__).resolve().parents[1]


def test_geo_aio_sro_reference_pack_is_registry_connected():
    registry = json.loads((ROOT / "knowledge" / "reference-registry.json").read_text())
    assert "geo-aeo-sro-expanded" in registry["packs"]

    entries = [
        entry for entry in registry["entries"] if entry["pack"] == "geo-aeo-sro-expanded"
    ]
    assert {entry["id"] for entry in entries} == {
        "sro-evidence-pipeline",
        "aeo-readiness-checks",
        "ai-visibility-observation-contract",
        "citation-opportunity-ethics",
    }
    body = (
        ROOT / registry["packs"]["geo-aeo-sro-expanded"]["path"]
    ).read_text(encoding="utf-8")
    for entry in entries:
        assert f'id="{entry["anchor"]}"' in body
        assert entry["affected_skills"]
        assert entry["affected_agents"]
    assert validate() == []


def test_geo_readiness_rubric_preserves_no_overclaim_policy():
    body = (ROOT / "knowledge" / "geo-readiness-rubric.md").read_text(encoding="utf-8")
    assert "SRO evidence pipeline" in body
    assert "AI visibility observation contract" in body
    assert "`llms.txt` presence is recorded as governance context only" in body
    assert "not as a Google Search boost" in body
    assert "Missing evidence creates an `UNKNOWN` state" in body
    assert "citation probability, certification, or guarantee" in body
