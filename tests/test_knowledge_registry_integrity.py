from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_reference_freshness import validate as validate_references


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def test_reference_registry_paths_sources_and_anchors_are_complete():
    registry = _json("knowledge/reference-registry.json")
    assert validate_references() == []

    packs = registry["packs"]
    entries_by_pack = {pack_id: 0 for pack_id in packs}
    for pack_id, pack in packs.items():
        pack_path = ROOT / pack["path"]
        assert pack_path.exists(), pack["path"]
        body = pack_path.read_text(encoding="utf-8")
        assert pack["owner"]
        assert pack["primary_sources"]
        assert "## Primary sources" in body

    for entry in registry["entries"]:
        entries_by_pack[entry["pack"]] += 1
        pack = packs[entry["pack"]]
        body = (ROOT / pack["path"]).read_text(encoding="utf-8")
        assert f'id="{entry["anchor"]}"' in body
        assert entry["affected_skills"]
        assert entry["affected_agents"]

    assert all(count > 0 for count in entries_by_pack.values())


def test_expanded_reference_packs_are_not_orphaned():
    registry = _json("knowledge/reference-registry.json")
    expanded = {
        pack_id
        for pack_id in registry["packs"]
        if pack_id.endswith("-expanded") or pack_id in {"sxo-cro-expanded"}
    }
    assert expanded

    connected = {
        entry["pack"]
        for entry in registry["entries"]
        if entry["affected_skills"] and entry["affected_agents"]
    }
    assert expanded <= connected
