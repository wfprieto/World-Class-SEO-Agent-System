from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from scripts.inventory_comparator import (
    COMPARATIVE,
    _catalog_skill_ids,
    _effective_inventory_hashes,
    _sha256,
    _skill_ids,
    inventory_repo,
    load_json,
    validate_all,
    validate_capability_inventory,
    validate_current_target_commits,
    validate_inventory_freshness,
    validate_parity_ledger,
    validate_scorecard,
    weighted_score,
)

ROOT = Path(__file__).resolve().parents[1]


def _registry_fixture(tmp_path: Path) -> Path:
    for relative in (
        "seoctl/command-registry.json",
        "seoctl/command-registry-overlay.json",
        "orchestration/capability-registry.json",
        "orchestration/product-proof-capability-overlay.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return tmp_path


def test_inventory_digest_is_stable_across_git_line_endings(tmp_path: Path):
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "value": 1\r\n}\r\n')

    assert _sha256(lf) == _sha256(crlf)


def test_skill_inventory_accepts_generated_evidence_annotations(tmp_path: Path):
    index = tmp_path / "SKILL_INDEX.md"
    index.write_text(
        "- `plain-skill`\n"
        "- `classified-skill` — `COMMAND_BACKED` / `REGISTRY_VERIFIED`\n"
        "- `packaged-skill` — `RUNTIME_CONTEXT` / `DOCUMENTED_ONLY` — package: `x#y`\n",
        encoding="utf-8",
    )

    assert _skill_ids(index) == {"plain-skill", "classified-skill", "packaged-skill"}


def test_generated_skill_index_matches_machine_catalog():
    assert _skill_ids(ROOT / "skills/SKILL_INDEX.md") == _catalog_skill_ids(
        ROOT / "skills/skill-catalog.json"
    )


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


def test_score_change_cannot_pass_by_recomputing_arithmetic() -> None:
    scorecard = load_json(COMPARATIVE / "world-class-baseline.json")
    broken = copy.deepcopy(scorecard)
    broken["categories"][0]["score"] = 8.8
    broken["overall_score"] = weighted_score(broken)

    assert "category scores differ from the reviewed score profile" in validate_scorecard(
        broken
    )


def test_scorecard_evidence_ids_and_digests_are_bound() -> None:
    scorecard = load_json(COMPARATIVE / "world-class-baseline.json")
    altered = copy.deepcopy(scorecard)
    altered["categories"][0]["evidence"][0]["claim"] = "Substituted claim"
    assert any("evidence digest mismatch" in error for error in validate_scorecard(altered))

    duplicate = copy.deepcopy(scorecard)
    first = duplicate["categories"][0]["evidence"][0]["id"]
    duplicate["categories"][1]["evidence"][0]["id"] = first
    assert "evidence ids must be non-empty and unique" in validate_scorecard(duplicate)


def test_scorecard_rejects_non_finite_scores() -> None:
    scorecard = load_json(COMPARATIVE / "world-class-baseline.json")
    scorecard["categories"][0]["score"] = float("nan")
    assert any("score must be finite" in error for error in validate_scorecard(scorecard))


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


def test_effective_inventory_hashes_bind_both_overlays(tmp_path: Path):
    root = _registry_fixture(tmp_path)
    parity = load_json(COMPARATIVE / "capability-parity.json")
    assert validate_inventory_freshness(parity, root) == []

    command_path = root / "seoctl/command-registry-overlay.json"
    command_overlay = load_json(command_path)
    command_overlay["commands"][0]["network"] = "none"
    command_path.write_text(json.dumps(command_overlay), encoding="utf-8")
    assert any(
        "effective_command_registry" in error
        for error in validate_inventory_freshness(parity, root)
    )

    shutil.copy2(ROOT / "seoctl/command-registry-overlay.json", command_path)
    capability_path = root / "orchestration/product-proof-capability-overlay.json"
    capability_overlay = load_json(capability_path)
    capability_overlay["agent_overrides"]["SEO Technical Agent"]["skills"].append("synthetic-drift")
    capability_path.write_text(json.dumps(capability_overlay), encoding="utf-8")
    assert any(
        "effective_capability_registry" in error
        for error in validate_inventory_freshness(parity, root)
    )


@pytest.mark.parametrize(
    ("relative_path", "mutation"),
    [
        ("seoctl/command-registry-overlay.json", "schema_version"),
        ("seoctl/command-registry-overlay.json", "unknown_top_level"),
        (
            "orchestration/product-proof-capability-overlay.json",
            "schema_version",
        ),
        (
            "orchestration/product-proof-capability-overlay.json",
            "unknown_top_level",
        ),
    ],
)
def test_effective_inventory_rejects_unsupported_overlay_contracts(
    tmp_path: Path, relative_path: str, mutation: str
):
    root = _registry_fixture(tmp_path)
    parity = load_json(COMPARATIVE / "capability-parity.json")
    path = root / relative_path
    overlay = load_json(path)
    if mutation == "schema_version":
        overlay["schema_version"] = "999.0.0"
    else:
        overlay["unrecognized_semantic_control"] = True
    path.write_text(json.dumps(overlay), encoding="utf-8")

    errors = validate_inventory_freshness(parity, root)

    assert any("effective inventory could not be merged" in error for error in errors)
    expected_detail = (
        "schema_version must be" if mutation == "schema_version" else "unknown top-level fields"
    )
    assert any(expected_detail in error for error in errors)


def test_effective_inventory_hash_ignores_json_formatting_and_unrelated_files(
    tmp_path: Path,
):
    root = _registry_fixture(tmp_path)
    before = _effective_inventory_hashes(root)
    for path in (*root.glob("seoctl/*.json"), *root.glob("orchestration/*.json")):
        payload = load_json(path)
        path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
    (root / "unrelated.txt").write_text("not an inventory\n", encoding="utf-8")
    assert _effective_inventory_hashes(root) == before


def test_gap_claim_cannot_contradict_canonical_command_inventory():
    ledger = load_json(COMPARATIVE / "capability-parity.json")
    broken = copy.deepcopy(ledger)
    row = next(item for item in broken["capabilities"] if item["id"] == "unified-command-surface")
    row["code_state"] = "ABSENT"

    errors = validate_capability_inventory(broken, ROOT)

    assert any(
        "unified-command-surface" in error and "effective command inventory" in error
        for error in errors
    )


def test_current_evidence_keeps_code_live_and_external_proof_separate():
    world = load_json(COMPARATIVE / "world-class-baseline.json")
    assert world["verification_state"] == {
        "code_verified": "PASS",
        "live_verified": "INCOMPLETE",
        "externally_reproduced": "NOT_RUN",
    }
