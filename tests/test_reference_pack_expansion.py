from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "knowledge" / "reference-registry.json"

EXPANDED_PACKS = {
    "technical-search-expanded",
    "content-quality-expanded",
    "local-maps-expanded",
    "ai-search-geo-expanded",
    "international-hreflang-expanded",
    "sxo-cro-expanded",
    "backlink-authority-expanded",
    "ecommerce-programmatic-expanded",
    "google-apis-expanded",
    "schema-rich-results-expanded",
}


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8-sig"))


def test_expanded_reference_packs_are_registry_connected():
    registry = _registry()
    assert EXPANDED_PACKS <= set(registry["packs"])

    entries_by_pack: dict[str, list[dict]] = {pack: [] for pack in EXPANDED_PACKS}
    for entry in registry["entries"]:
        if entry["pack"] in entries_by_pack:
            entries_by_pack[entry["pack"]].append(entry)

    for pack_id, entries in entries_by_pack.items():
        pack = registry["packs"][pack_id]
        body = (ROOT / pack["path"]).read_text(encoding="utf-8")
        assert entries, f"{pack_id} has no registry entries"
        assert "Evidence posture:" in body
        assert pack["owner"]
        assert pack["primary_sources"]
        for entry in entries:
            assert entry["affected_agents"]
            assert entry["affected_skills"]
            assert f'id="{entry["anchor"]}"' in body


def test_expanded_reference_registry_still_validates():
    assert validate() == []
