from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.plan_github_controls_rollback import REPOSITORY, build_plan


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / f"evaluation/remediation/{name}").read_text(encoding="utf-8"))


def test_provider_rollback_plan_is_exact_and_flags_security_downgrades() -> None:
    plan = build_plan(
        _load("phase1-provider-baseline.json"), _load("phase1-provider-evidence.json")
    )
    settings = {item["setting"]: item for item in plan["changes"]}
    assert set(settings) == {
        "private_vulnerability_reporting",
        "discussions",
        "vulnerability_alerts",
        "dependabot_security_updates",
        "ruleset",
    }
    assert settings["private_vulnerability_reporting"]["security_downgrade"] is True
    assert settings["ruleset"]["restore"]["required_approving_review_count"] == 0
    assert plan["repository"] == REPOSITORY
    assert plan["mode"] == "DRY_RUN"


def test_provider_rollback_rejects_wrong_repository() -> None:
    baseline = _load("phase1-provider-baseline.json")
    current = _load("phase1-provider-evidence.json")
    current["repository"] = "attacker/wrong-repository"
    with pytest.raises(ValueError, match="does not match"):
        build_plan(baseline, current)
