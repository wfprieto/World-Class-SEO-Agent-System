#!/usr/bin/env python3
"""Validate the read-only scheduled maintenance workflow contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = Path(".github/workflows/maintenance.yml")
SHA = re.compile(r"^[^/@\s]+/[^/@\s]+@[0-9a-f]{40}$")
REQUIRED_COMMANDS = {
    "python scripts/validate_scheduled_maintenance.py",
    "python scripts/validate_open_issue_remediation.py",
    "python scripts/validate_reference_freshness.py",
    "python scripts/validate_dependency_lock.py",
    "python scripts/validate_repository_operations.py",
    "python scripts/validate_repository_governance.py",
    "python scripts/inventory_comparator.py",
    "python scripts/validate_architecture_exception_disposition.py",
}


def _load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("scheduled maintenance workflow must contain a mapping")
    if True in payload and "on" not in payload:
        payload["on"] = payload.pop(True)
    return payload


def _trigger_errors(workflow: dict[str, Any]) -> list[str]:
    trigger = workflow.get("on")
    if not isinstance(trigger, dict):
        return ["scheduled maintenance requires explicit triggers"]
    errors = []
    if set(trigger) != {"schedule", "workflow_dispatch"}:
        errors.append("scheduled maintenance triggers must be schedule and workflow_dispatch only")
    schedule = trigger.get("schedule")
    if not isinstance(schedule, list) or len(schedule) != 1:
        errors.append("scheduled maintenance requires exactly one cadence")
    return errors


def _checkout_errors(step: dict[str, Any], reference: object) -> list[str]:
    if not isinstance(reference, str) or not reference.startswith("actions/checkout@"):
        return []
    expected = {
        "fetch-depth": 0,
        "fetch-tags": True,
        "persist-credentials": False,
        "ref": "${{ github.sha }}",
    }
    return (
        ["scheduled maintenance checkout settings must remain exact"]
        if step.get("with") != expected
        else []
    )


def _step_errors(steps: object) -> list[str]:
    if not isinstance(steps, list):
        return ["scheduled maintenance steps must be a list"]
    errors: list[str] = []
    commands: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            errors.append("scheduled maintenance step must be a mapping")
            continue
        if step.get("continue-on-error") is not None or step.get("if") is not None:
            errors.append("scheduled maintenance steps must be unconditional and fail closed")
        reference = step.get("uses")
        if isinstance(reference, str) and not SHA.fullmatch(reference):
            errors.append(f"scheduled maintenance action is mutable: {reference}")
        command = step.get("run")
        if isinstance(command, str):
            commands.add(command.strip())
        errors.extend(_checkout_errors(step, reference))
    missing = sorted(REQUIRED_COMMANDS - commands)
    if missing:
        errors.append("scheduled maintenance commands are missing: " + ", ".join(missing))
    if not any("tests/test_open_issue_remediation.py" in command for command in commands):
        errors.append("scheduled maintenance mutation suite is missing")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    try:
        workflow = _load(root / WORKFLOW)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)]
    errors = _trigger_errors(workflow)
    if workflow.get("permissions") != {"contents": "read"}:
        errors.append("scheduled maintenance permissions must be exact read-only contents")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {"static-maintenance"}:
        return errors + ["scheduled maintenance requires one canonical job"]
    job = jobs["static-maintenance"]
    if not isinstance(job, dict):
        return errors + ["scheduled maintenance canonical job must be a mapping"]
    if job.get("runs-on") != "ubuntu-latest" or job.get("timeout-minutes") != 20:
        errors.append("scheduled maintenance runner and timeout must remain bounded")
    errors.extend(_step_errors(job.get("steps")))
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
