from __future__ import annotations

from pathlib import Path

import yaml


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
    step = next(step for step in _rollback_steps() if step.get("name") == "Validate restored baseline repository")

    assert step["env"]["PYTHONPATH"] == "${{ github.workspace }}"
