from __future__ import annotations

import json
from pathlib import Path

from scripts.run_improvement_cycle import evaluate_cycle

ROOT = Path(__file__).resolve().parents[1]


def test_every_persisted_approved_cycle_reproduces_approval():
    cycle_dir = ROOT / "evaluation" / "cycles"
    for path in sorted(cycle_dir.glob("*.json")):
        cycle = json.loads(path.read_text(encoding="utf-8"))
        result = evaluate_cycle(
            cycle,
            builder_context_id=cycle["builder_context_id"],
        )
        if cycle["state"] == "APPROVED_GREAT":
            assert result["decision"] == "APPROVE_GREAT", (
                path,
                result,
            )
        assert result["direct_merge_permitted"] is False


def test_persisted_cycle_hash_tampering_is_detected():
    path = ROOT / "evaluation" / "cycles" / "cycle-0001.json"
    cycle = json.loads(path.read_text(encoding="utf-8"))
    cycle["verification"]["evidence_refs"].append("unreviewed-new-evidence")
    result = evaluate_cycle(
        cycle,
        builder_context_id=cycle["builder_context_id"],
    )
    assert result["decision"] == "REWORK_GOOD"
    assert any("different evidence package" in error for error in result["errors"])
