from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_checklist_triage_blocks_unverified_rule_promotion():
    body = (
        ROOT / "knowledge" / "reference-packs" / "legacy-checklist-triage.md"
    ).read_text(encoding="utf-8")
    assert "needs-primary-source-confirmation" in body
    assert "Only `current` items with matching evidence" in body
    assert "must not block releases or claim ranking impact" in body


def test_crawl_budget_logfile_pack_requires_materiality_evidence():
    body = (
        ROOT / "knowledge" / "reference-packs" / "crawl-budget-logfile-expanded.md"
    ).read_text(encoding="utf-8")
    assert "A small crawl does not prove a crawl-budget problem" in body
    assert "User-agent strings alone are not security proof" in body
    assert "business-priority templates" in body


def test_libhunt_reference_packs_are_registry_connected():
    registry = json.loads((ROOT / "knowledge" / "reference-registry.json").read_text())
    for pack_id in ("legacy-checklist-triage", "crawl-budget-logfile-expanded"):
        assert pack_id in registry["packs"]
        entries = [entry for entry in registry["entries"] if entry["pack"] == pack_id]
        assert entries
        pack_body = (ROOT / registry["packs"][pack_id]["path"]).read_text(encoding="utf-8")
        for entry in entries:
            assert f'id="{entry["anchor"]}"' in pack_body
            assert entry["affected_skills"]
            assert entry["affected_agents"]
    assert validate() == []
