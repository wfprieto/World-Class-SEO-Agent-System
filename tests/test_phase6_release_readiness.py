from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_phase6_readiness import validate

ROOT = Path(__file__).resolve().parents[1]


def test_phase6_artifacts_are_consistent():
    assert validate() == []


def test_release_is_truthfully_blocked_until_external_gates_pass():
    data = json.loads((ROOT / "evaluation/comparative/final-release-readiness.json").read_text(encoding="utf-8"))
    assert data["release_decision"] == "BLOCKED"
    assert data["gates"]["seven_archetype_benchmark"] == "NOT_RUN"
    assert data["gates"]["external_reproduction"] == "NOT_RUN"


def test_benchmark_framework_covers_required_scope():
    data = json.loads((ROOT / "evaluation/comparative/benchmark-cases.json").read_text(encoding="utf-8"))
    assert len(data["archetypes"]) == 7
    assert len(data["tasks"]) == 15
    assert data["gates"]["unsupported_claims_max"] == 0
