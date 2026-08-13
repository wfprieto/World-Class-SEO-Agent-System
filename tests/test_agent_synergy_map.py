from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNERGY = ROOT / "orchestration" / "agent-synergy-map.json"
PROOF = ROOT / "examples" / "proof-pack" / "proof-pack-manifest.json"

REQUIRED_GLOBAL_STEPS = {
    "intake",
    "route",
    "evidence_collect",
    "specialist_execute",
    "cross_agent_handoff",
    "scrummaster_challenge",
    "plain_language_report",
    "verification_plan",
    "learning_record",
}

REQUIRED_GOVERNANCE_AGENTS = {
    "SEO Scrummaster Agent",
    "Senior SEO Strategist Agent",
    "SEO Output Report Agent",
    "AI Principal SEO Scientist",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_synergy_map_references_known_agents_workflows_and_proof_units() -> None:
    synergy = _json(SYNERGY)
    capability = _json(ROOT / "orchestration" / "capability-registry.json")
    proof = _json(PROOF)
    known_agents = set(capability["agents"])
    proof_units = {unit["id"] for unit in proof["proof_units"]}

    assert REQUIRED_GLOBAL_STEPS <= set(synergy["global_loop"])
    assert REQUIRED_GOVERNANCE_AGENTS <= set(synergy["required_governance_agents"])

    for agent in synergy["required_governance_agents"]:
        assert agent in known_agents

    for workflow in synergy["workflows"]:
        assert workflow["lead_agent"] in known_agents
        assert workflow["final_output_owner"] in known_agents
        assert (ROOT / workflow["workflow_file"]).exists(), workflow["workflow_file"]
        assert set(workflow["support_agents"]) <= known_agents
        assert set(workflow["proof_units"]) <= proof_units


def test_synergy_handoffs_use_known_agents_and_contracts() -> None:
    synergy = _json(SYNERGY)
    capability = _json(ROOT / "orchestration" / "capability-registry.json")
    known_agents = set(capability["agents"])

    for rule in synergy["handoff_rules"]:
        assert rule["id"]
        assert rule["when"]
        assert rule["handoff_to"] in known_agents
        if "required_payload" in rule:
            assert (ROOT / rule["required_payload"]).exists()
        if "required_skill" in rule:
            skills = {
                skill
                for category in _json(ROOT / "skills" / "skill-catalog.json")["categories"]
                for skill in category["skills"]
            }
            assert rule["required_skill"] in skills


def test_system_map_surfaces_synergy_contract() -> None:
    system_map = (ROOT / "SYSTEM_MAP.md").read_text(encoding="utf-8")
    docs_map = (ROOT / "docs" / "AGENT-SYNERGY-MAP.md").read_text(encoding="utf-8")

    assert "docs/AGENT-SYNERGY-MAP.md" in system_map
    assert "orchestration/agent-synergy-map.json" in system_map
    assert "SEO Scrummaster Agent" in docs_map
    assert "SEO Output Report Agent" in docs_map
    assert "AI Principal SEO Scientist" in docs_map
