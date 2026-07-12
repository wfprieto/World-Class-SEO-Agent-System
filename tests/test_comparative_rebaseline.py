from __future__ import annotations

import copy
from pathlib import Path

from scripts.inventory_comparator import (
    COMPARATIVE,
    inventory_repo,
    load_json,
    validate_all,
    validate_parity_ledger,
    validate_scorecard,
    weighted_score,
)

ROOT = Path(__file__).resolve().parents[1]


def test_comparative_rebaseline_is_valid_and_reproducible():
    result = validate_all(ROOT)
    assert result["status"] == "PASS", result["errors"]
    assert result["scores"] == {
        "world_class": 70.0,
        "claude_seo": 80.0,
        "gap": 10.0,
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
    assert weighted_score(scorecard) == 70.0
    broken = copy.deepcopy(scorecard)
    broken["overall_score"] = 73.0
    errors = validate_scorecard(broken)
    assert any("formula produces 70.0" in error for error in errors)


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
