from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate as validate_references


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_all_reference_pack_files_are_registered():
    assert validate_references() == []
    registry = _json("knowledge/reference-registry.json")
    registered = {
        (ROOT / pack["path"]).resolve()
        for pack in registry["packs"].values()
    }
    actual = {
        path.resolve()
        for path in (ROOT / "knowledge" / "reference-packs").glob("*.md")
    }
    assert actual <= registered


def test_registered_packs_have_entries_and_existing_primary_sources():
    registry = _json("knowledge/reference-registry.json")
    entries_by_pack = {pack_id: [] for pack_id in registry["packs"]}
    for entry in registry["entries"]:
        entries_by_pack[entry["pack"]].append(entry)

    for pack_id, pack in registry["packs"].items():
        assert entries_by_pack[pack_id], pack_id
        assert pack["primary_sources"], pack_id
        assert (ROOT / pack["path"]).exists(), pack["path"]


def test_framework_pack_is_not_only_documented_it_is_registry_addressable():
    registry = _json("knowledge/reference-registry.json")
    assert "framework-seo-implementation-expanded" in registry["packs"]
    ids = {
        entry["id"]
        for entry in registry["entries"]
        if entry["pack"] == "framework-seo-implementation-expanded"
    }
    assert ids == {
        "framework-metadata-boundary",
        "structured-data-component-gate",
        "sitemap-generation-patterns",
        "adapter-hardening-patterns",
    }
