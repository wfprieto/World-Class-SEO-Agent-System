from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def _catalog_skills() -> set[str]:
    catalog = _json("skills/skill-catalog.json")
    return {skill for category in catalog["categories"] for skill in category["skills"]}


def test_capability_registry_agent_files_and_assets_exist():
    registry = _json("orchestration/capability-registry.json")
    known_skills = _catalog_skills()
    agent_index = (ROOT / "agents" / "AGENT_INDEX.md").read_text(encoding="utf-8")

    for agent_name, bundle in registry["agents"].items():
        assert agent_name in agent_index
        assert (ROOT / bundle["agent_file"]).exists(), bundle["agent_file"]
        assert set(bundle["skills"]) <= known_skills
        for key in ("skill_files", "knowledge_files", "templates"):
            for relative_path in bundle.get(key, []):
                assert (ROOT / relative_path).exists(), f"{agent_name}: {relative_path}"
        assert bundle["required_evidence"], agent_name


def test_reference_registry_agents_are_known_to_capability_or_index():
    capabilities = _json("orchestration/capability-registry.json")
    known_agents = set(capabilities["agents"])
    agent_index = (ROOT / "agents" / "AGENT_INDEX.md").read_text(encoding="utf-8")
    registry = _json("knowledge/reference-registry.json")

    for entry in registry["entries"]:
        for agent in entry["affected_agents"]:
            assert agent in known_agents or agent in agent_index
