"""Durable rollback and exact immutable remediation closure history."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__:
    from scripts.remediation_contracts import (
        PHASE_IDS,
        PROGRAM_PATH,
        ROOT,
        _load_object,
    )
else:
    from remediation_contracts import (
        PHASE_IDS,
        PROGRAM_PATH,
        ROOT,
        _load_object,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_squash_integration import (
        closure_history_head,
    )
else:
    from remediation_squash_integration import (
        closure_history_head,
    )


def _baseline_tree_errors(
    payload: dict[str, Any], root: Path, baseline: str, label: str
) -> list[str]:
    errors: list[str] = []
    if (root / ".git").exists() and baseline:
        try:
            baseline_tree = subprocess.check_output(
                ["git", "rev-parse", f"{baseline}^{{tree}}"],
                cwd=root,
                text=True,
                timeout=20,
            ).strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            errors.append(f"{label} cannot resolve the baseline tree")
        else:
            if payload.get("expected_baseline_tree") != baseline_tree:
                errors.append(f"{label} expected_baseline_tree does not match baseline_commit")
    return errors


def _rollback_evidence_errors(
    payload: dict[str, Any], program: dict[str, Any], root: Path, label: str
) -> list[str]:
    """Reject stale, partial, or snapshot-specific durable rollback instructions."""
    errors: list[str] = []
    required_fields = {
        "schema_version",
        "phase_id",
        "strategy",
        "baseline_commit",
        "candidate_selector",
        "commit_range",
        "revert_order",
        "expected_baseline_tree",
        "workflow",
        "job",
        "required_assertions",
        "recovery_position",
        "limitations",
    }
    if set(payload) != required_fields:
        errors.append(f"{label} fields do not match the canonical durable procedure")
    phase_id = str(payload.get("phase_id", ""))
    phase: dict[str, Any] = next(
        (item for item in program.get("phases", []) if item.get("id") == phase_id), {}
    )
    baseline_commit = phase.get("rollback_baseline_commit")
    if phase_id == "P0" and not baseline_commit:
        baseline_commit = program.get("baseline", {}).get("commit")
    expected_values = {
        "schema_version": "3.0.0",
        "phase_id": phase_id,
        "strategy": "DYNAMIC_EXACT_SNAPSHOT",
        "baseline_commit": baseline_commit,
        "candidate_selector": "review_snapshot_commit",
        "commit_range": "baseline_commit..review_snapshot_commit",
        "revert_order": "newest_first",
        "workflow": ".github/workflows/validate.yml",
        "job": (
            "phase0-rollback-certification" if phase_id == "P0" else "phase-rollback-certification"
        ),
        "recovery_position": (
            "Resolve review_snapshot_commit from the canonical program, enumerate git rev-list "
            "<baseline_commit>..<review_snapshot_commit>, and revert every returned commit "
            "newest-to-oldest as one bounded operation."
        ),
    }
    for key, expected in expected_values.items():
        if payload.get(key) != expected:
            errors.append(f"{label} {key} is stale or unsafe")
    required_assertions = {
        "candidate_equals_review_snapshot_commit",
        "all_commits_in_baseline_exclusive_range_reverted",
        "post_revert_tree_equals_baseline_tree",
        "baseline_validation_passes",
    }
    if set(payload.get("required_assertions", [])) != required_assertions:
        errors.append(f"{label} does not require every rollback safety assertion")
    if not phase:
        errors.append(f"{label} phase_id does not identify a program phase")
    if not baseline_commit:
        errors.append(f"{label} phase has no rollback_baseline_commit")
    baseline = str(baseline_commit or "")
    errors.extend(_baseline_tree_errors(payload, root, baseline, label))
    return errors


def _normalize_closure_delta(
    closure: dict[str, Any], snapshot: dict[str, Any], phase: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_copy = json.loads(json.dumps(closure))
    snapshot_copy = json.loads(json.dumps(snapshot))
    phase_id = str(phase.get("id"))
    current_phase = next(item for item in current_copy["phases"] if item["id"] == phase_id)
    snapshot_phase = next(item for item in snapshot_copy["phases"] if item["id"] == phase_id)
    for key in (
        "status",
        "review",
        "review_snapshot_commit",
        "frozen_package_commit",
        "package_certification",
    ):
        current_phase[key] = snapshot_phase.get(key)
    current_copy["current_phase"] = snapshot_copy["current_phase"]
    phase_index = PHASE_IDS.index(phase_id)
    if phase_index + 1 < len(PHASE_IDS):
        next_id = PHASE_IDS[phase_index + 1]
        next_current = next(item for item in current_copy["phases"] if item["id"] == next_id)
        next_snapshot = next(item for item in snapshot_copy["phases"] if item["id"] == next_id)
        next_current["status"] = next_snapshot["status"]
    return current_copy, snapshot_copy


def _closure_delta_errors(
    program: dict[str, Any], phase: dict[str, Any], root: Path, snapshot_commit: str
) -> list[str]:
    errors: list[str] = []
    if not (root / ".git").exists():
        return errors
    try:
        history_head = closure_history_head(
            root, str(program.get("baseline", {}).get("commit", "")), snapshot_commit
        )
        descendants = subprocess.check_output(
            [
                "git",
                "rev-list",
                "--reverse",
                "--ancestry-path",
                f"{snapshot_commit}..{history_head}",
            ],
            cwd=root,
            text=True,
            timeout=20,
        ).splitlines()
        if not descendants:
            return ["closure commit is missing after the immutable review snapshot"]
        closure_commit = descendants[0]
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", f"{snapshot_commit}..{closure_commit}"],
            cwd=root,
            text=True,
            timeout=20,
        ).splitlines()
        allowed_path = str(PROGRAM_PATH.relative_to(ROOT)).replace("\\", "/")
        if set(changed) - {allowed_path}:
            errors.append("closure changes files outside the canonical remediation program")
        snapshot = _load_object_at_commit(root, allowed_path, snapshot_commit)
        closure = _load_object_at_commit(root, allowed_path, closure_commit)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ["closure cannot load the immutable review snapshot"]

    current_copy, snapshot_copy = _normalize_closure_delta(closure, snapshot, phase)
    if current_copy != snapshot_copy:
        errors.append("closure delta contains fields outside the status-and-verdict allowlist")
    return errors


def _load_object_at_commit(root: Path, source_path: str, commit: str | None) -> dict[str, Any]:
    if (root / ".git").exists() and commit:
        content = subprocess.check_output(
            ["git", "show", f"{commit}:{source_path}"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        payload = json.loads(content.decode("utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"{source_path} must contain a JSON object")
        return payload
    return _load_object(root / source_path)
