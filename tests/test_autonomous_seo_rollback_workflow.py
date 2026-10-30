from __future__ import annotations

from pathlib import Path

import yaml

from scripts.validate_historical_rollback_claims import APPROVED_BOUNDARIES

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "autonomous-seo-certification.yml"


def _workflow() -> dict:
    payload = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _rollback_steps() -> list[dict]:
    workflow = _workflow()
    jobs = workflow["jobs"]
    return jobs["autonomous-seo-p0-rollback-certification"]["steps"]


def test_restored_baseline_validation_has_an_explicit_package_root() -> None:
    steps = _rollback_steps()
    name = "Validate restored baseline repository with scoped freshness"
    index = next(index for index, step in enumerate(steps) if step.get("name") == name)
    step = steps[index]

    assert step["env"]["PYTHONPATH"] == "${{ github.workspace }}"
    assert steps[index - 1]["name"] == "Prove exact restored autonomous baseline"
    assert steps[index - 2]["name"] == "Install baseline validation dependencies"
    assert steps[index + 1]["name"] == "Prove exact restored autonomous baseline"
    assert "validate_historical_rollback_claims.py" in step["run"]
    assert "WCSEO_BASELINE_CLAIM_VALIDATOR" in step["run"]
    assert "WCSEO_ROLLBACK_EXPECTED_SHA" in step["run"]
    assert "finally" in step["run"]


def test_autonomous_rollback_preserves_historical_wrapper_before_checkout() -> None:
    step = next(
        step
        for step in _rollback_steps()
        if step.get("name") == "Preserve trusted source-integrity validator"
    )
    assert "validate_source_integrity.py" in step["run"]
    assert "validate_historical_rollback_claims.py" in step["run"]
    assert "4350c3716f6da11e0f57ddf85997c096b2e0c8fd" in APPROVED_BOUNDARIES
