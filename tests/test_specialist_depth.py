from __future__ import annotations

from pathlib import Path

import pytest

from runtime.capability_resolver import CapabilityResolver
from runtime.specialist_decision import (
    SpecialistDecisionError,
    decision_artifact,
    specialist_output_errors,
)
from scripts.validate_specialist_depth import (
    PRIORITY_AGENTS,
    run_mutation_suite,
    validate_repository,
)

ROOT = Path(__file__).resolve().parents[1]


def test_priority_specialists_have_validated_decision_depth() -> None:
    assert validate_repository(ROOT) == []


def test_specialist_depth_mutations_are_all_killed() -> None:
    result = run_mutation_suite(ROOT)
    assert result["status"] == "PASS"
    assert result["mutants"] == result["killed"] == 21


def test_known_answer_branches_use_runtime_loaded_safety_rules() -> None:
    resolver = CapabilityResolver(ROOT)
    cases = (
        (
            {"required_evidence_available": True, "material_harm": False},
            ("READY", "COMPLETE", False),
        ),
        (
            {"required_evidence_available": True, "material_harm": True},
            ("ESCALATE", "BLOCKED", True),
        ),
        (
            {"required_evidence_available": False, "material_harm": True},
            ("ESCALATE", "BLOCKED", True),
        ),
        (
            {"required_evidence_available": False, "material_harm": False},
            ("BLOCKED", "BLOCKED", False),
        ),
    )
    for agent in PRIORITY_AGENTS:
        context = resolver.load_context(agent)["skill_context"]
        for signals, expected in cases:
            artifact = decision_artifact(
                agent=agent,
                skill_context=context,
                evidence_refs=["known-answer-fixture"],
                **signals,
            )
            assert (
                artifact["state"],
                artifact["mapped_execution_state"],
                artifact["human_action_required"],
            ) == expected


def test_runtime_decision_artifact_rejects_token_complete_nonsense() -> None:
    agent = "Negative SEO & Security Agent"
    context = CapabilityResolver(ROOT).load_context(agent)["skill_context"]
    weakened = [dict(row) for row in context]
    for row in weakened:
        if row["path"].startswith("skills/specialist-depth-playbooks.md#"):
            markers = (
                "never submit a disavow automatically\n"
                "ABSTAIN` from attacker identity or causation\n"
            )
            row["content"] = (
                "## Agent: `Negative SEO & Security Agent`\n"
                "### Decision branches\nNONSENSE\n"
                "### Evidence sufficiency\nNONSENSE\n"
                "### Failure, abstention, and escalation\n`BLOCKED` `ABSTAIN`\n"
                f"### Edge cases and examples\n{markers}Good: x Bad: y"
            )
    with pytest.raises(SpecialistDecisionError, match="digest mismatch"):
        decision_artifact(
            agent=agent,
            skill_context=weakened,
            required_evidence_available=True,
            material_harm=False,
        )


def test_specialist_output_mapping_is_machine_enforced() -> None:
    output = {
        "agent": "SEO Accessibility Agent",
        "execution_state": "BLOCKED",
        "specialist_decision": {
            "state": "READY",
            "mapped_execution_state": "COMPLETE",
            "human_action_required": False,
            "evidence_refs": [],
        },
    }
    assert any("conflicts" in error for error in specialist_output_errors(output))


def test_runtime_loads_exact_missing_skill_sections_and_not_whole_fallback_file() -> None:
    resolver = CapabilityResolver(ROOT)
    context = resolver.load_context("Negative SEO & Security Agent")
    by_path = {row["path"]: row["content"] for row in context["skill_context"]}

    for skill in ("negative-seo-threat-review", "security-indexation-check", "spam-policy-check"):
        path = f"skills/missing-skills.md#{skill}"
        assert path in by_path
        assert by_path[path].startswith(f"## `{skill}`")
        assert by_path[path].count("\n## ") == 0


def test_each_specialist_receives_only_its_exact_playbook_section() -> None:
    resolver = CapabilityResolver(ROOT)
    for agent in PRIORITY_AGENTS:
        context = resolver.load_context(agent)
        integrity = [
            row for row in context["skill_context"]
            if row["path"] == "governance/specialist-playbook-integrity.json"
        ]
        playbooks = [
            row for row in context["skill_context"]
            if row["path"].startswith("skills/specialist-depth-playbooks.md#")
        ]
        assert len(integrity) == 1
        assert len(playbooks) == 1
        assert playbooks[0]["path"].endswith(f"#{agent}")
        assert playbooks[0]["content"].startswith(f"## Agent: `{agent}`")
        assert playbooks[0]["content"].count("\n## Agent:") == 0


def test_non_priority_agent_does_not_receive_specialist_playbook_overhead() -> None:
    context = CapabilityResolver(ROOT).load_context("SEO Technical Agent")
    paths = [row["path"] for row in context["skill_context"]]
    assert "skills/specialist-decision-standard.md" not in paths
    assert "governance/specialist-playbook-integrity.json" not in paths
    assert not any(path.startswith("skills/specialist-depth-playbooks.md#") for path in paths)


def test_runtime_resolves_previously_unwired_priority_definitions() -> None:
    resolver = CapabilityResolver(ROOT)
    cases = {
        "SEO Accessibility Agent": {"accessibility-audit"},
        "International & Multilingual SEO Agent": {
            "international-url-architecture",
            "localized-content-review",
            "regional-keyword-map",
        },
        "Local SEO Agent": {"citation-audit"},
        "Predictive SEO Trend Agent": {"trend-monitor", "forecasting", "content-calendar"},
        "Competitive Intelligence Agent": {"competitive-gap", "competitor-change-monitor"},
        "SEO Compliance & Legal Agent": {"spam-policy-check", "claims-risk-review"},
    }
    for agent, skills in cases.items():
        paths = {row["path"] for row in resolver.load_context(agent)["skill_context"]}
        for skill in skills:
            assert f"skills/missing-skills.md#{skill}" in paths
