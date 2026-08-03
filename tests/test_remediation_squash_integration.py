from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.remediation_squash_integration import (
    RECEIPT_PATH,
    validate_squash_integration,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e8c37abb5e939d4433e42ea8a02af63549ca0010"


def _receipt() -> dict[str, object]:
    return json.loads((ROOT / RECEIPT_PATH).read_text(encoding="utf-8"))


def test_canonical_squash_integration_is_exact_and_reachable() -> None:
    context, errors = validate_squash_integration(ROOT, BASELINE)

    assert errors == []
    assert context is not None
    assert context.source_closure == "0db24cfffb8d1af5d946f564762ed6126bab5ad4"
    assert context.target_commit == "98e8b4eef21dcc641361aed38cc29e7c25e590dc"


def test_same_tree_cannot_bypass_the_exact_tag_object() -> None:
    payload = _receipt()
    mutated = copy.deepcopy(payload)
    mutated["source"]["evidence_tag"]["object_sha"] = "0" * 40  # type: ignore[index]

    context, errors = validate_squash_integration(ROOT, BASELINE, payload=mutated)

    assert context is None
    assert any("tag object" in error for error in errors)


def test_target_tree_and_parent_are_both_authenticated() -> None:
    payload = _receipt()
    mutated = copy.deepcopy(payload)
    mutated["target"]["tree_sha"] = "0" * 40  # type: ignore[index]
    mutated["target"]["parent_commit"] = "1" * 40  # type: ignore[index]

    context, errors = validate_squash_integration(ROOT, BASELINE, payload=mutated)

    assert context is None
    assert any("target tree" in error for error in errors)


def test_wrong_program_baseline_is_rejected() -> None:
    context, errors = validate_squash_integration(ROOT, "f" * 40)

    assert context is None
    assert any("baseline" in error for error in errors)
