from __future__ import annotations

import copy
from pathlib import Path

from scripts.inventory_comparator import (
    COMPARATIVE,
    inventory_repo,
    load_json,
    validate_all,
    validate_capability_inventory,
    validate_current_target_commits,
    validate_parity_ledger,
    validate_scorecard,
    weighted_score,
)

ROOT = Path(__file__).resolve().parents[1]


def test_comparative_rebaseline_is_valid_and_reproducible():
    result = validate_all(ROOT)
    assert result["status"] == "PASS", result["errors"]
    assert result["scores"] == {
        "world_class": 69.9,
        "claude_seo": 80.0,
        "gap": 10.1,
        "target": 92.0,
    }
    assert result["open_capabilities"] > 0


def test_local_inventory_proves_current_runtime_baseline_without_hardcoded_file_counts():
    inventory = inventory_repo(ROOT)
    assert inventory["agent_files"] == 25
    assert inventory["indexed_skills"] >= 80
    assert inventory["python_scripts"] >= 9
    assert inventory["python_adapters"] >= 20
    assert inventory["test_functions"] >= 200
    assert inventory["workflow_files"] >= 5


def test_scorecard_formula_cannot_be_changed_or_miscalculated():
    scorecard = load_json(COMPARATIVE / "world-class-baseline.json")
    assert weighted_score(scorecard) == 69.9
    broken = copy.deepcopy(scorecard)
    broken["overall_score"] = 73.0
    errors = validate_scorecard(broken)
    assert any("formula produces 69.9" in error for error in errors)


def test_documentation_or_stub_maturity_cannot_claim_world_class_score():
    scorecard = load_json(COMPARATIVE / "world-class-baseline.json")
    broken = copy.deepcopy(scorecard)
    broken["categories"][4]["score"] = 9.0
    broken["overall_score"] = weighted_score(broken)
    errors = validate_scorecard(broken)
    assert any("exceeds maturity ceiling" in error for error in errors)


def test_every_open_capability_has_owner_pr_and_acceptance_criteria():
    ledger = load_json(COMPARATIVE / "capability-parity.json")
    assert validate_parity_ledger(ledger) == []
    for row in ledger["capabilities"]:
        assert row["acceptance"]
        if row["status"] == "GAP_OPEN":
            assert row["target_pr"].startswith("PR")


def test_closed_capability_requires_evidence():
    ledger = load_json(COMPARATIVE / "capability-parity.json")
    broken = copy.deepcopy(ledger)
    row = next(item for item in broken["capabilities"] if item["status"] != "GAP_OPEN")
    row["evidence"] = []
    errors = validate_parity_ledger(broken)
    assert any("claims closure without evidence" in error for error in errors)


def test_capability_ids_are_unique():
    ledger = load_json(COMPARATIVE / "capability-parity.json")
    ids = [row["id"] for row in ledger["capabilities"]]
    assert len(ids) == len(set(ids))


def test_comparative_artifacts_fail_closed_when_target_commit_is_stale():
    world = load_json(COMPARATIVE / "world-class-baseline.json")
    parity = load_json(COMPARATIVE / "capability-parity.json")
    readiness = load_json(COMPARATIVE / "final-release-readiness.json")
    world["target_repository"] = "wfprieto/World-Class-SEO-Agent-System@" + ("0" * 40)

    errors = validate_current_target_commits(world, parity, readiness, ROOT)

    assert any("world-class target commit is stale" in error for error in errors)


def test_gap_claim_cannot_contradict_canonical_command_inventory():
    ledger = load_json(COMPARATIVE / "capability-parity.json")
    broken = copy.deepcopy(ledger)
    row = next(item for item in broken["capabilities"] if item["id"] == "unified-command-surface")
    row["code_state"] = "ABSENT"

    errors = validate_capability_inventory(broken, ROOT)

    assert any("unified-command-surface" in error and "canonical command inventory" in error for error in errors)


def test_current_evidence_keeps_code_live_and_external_proof_separate():
    world = load_json(COMPARATIVE / "world-class-baseline.json")
    assert world["verification_state"] == {
        "code_verified": "PASS",
        "live_verified": "INCOMPLETE",
        "externally_reproduced": "NOT_RUN",
    }
