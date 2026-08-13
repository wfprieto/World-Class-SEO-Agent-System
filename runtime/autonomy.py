"""Evaluate SEO actions against the public autonomy safety policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.assets import resolve_asset_root

ROOT = resolve_asset_root(Path(__file__).resolve().parents[1])
POLICY = ROOT / "orchestration" / "autonomy-safety-policy.json"


@dataclass(frozen=True)
class AutonomyDecision:
    action_id: str
    mode: str
    allowed: bool
    approval_required: bool
    rollback_required: bool
    matched_dangerous_action: str | None
    reason: str


def load_policy(path: Path = POLICY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("autonomy safety policy must be a JSON object")
    return payload


def _mode_level(policy: dict[str, Any], mode: str) -> int:
    for row in policy["modes"]:
        if row["id"] == mode:
            return int(row["level"])
    raise ValueError(f"unknown autonomy mode: {mode}")


def _matches(patterns: list[str], proposed_action: str) -> bool:
    normalized = proposed_action.lower()
    return any(pattern.lower() in normalized for pattern in patterns)


def evaluate_action(
    proposed_action: str,
    *,
    mode: str = "mode_0_audit_only",
    approved: bool = False,
    policy: dict[str, Any] | None = None,
) -> AutonomyDecision:
    active_policy = policy or load_policy()
    current_level = _mode_level(active_policy, mode)

    for dangerous in active_policy["dangerous_actions"]:
        if not _matches(list(dangerous["patterns"]), proposed_action):
            continue
        minimum_level = _mode_level(active_policy, str(dangerous["minimum_mode"]))
        approval_required = bool(dangerous["requires_approval"])
        rollback_required = bool(dangerous["requires_rollback"])
        if current_level < minimum_level:
            return AutonomyDecision(
                action_id=str(dangerous["id"]),
                mode=mode,
                allowed=False,
                approval_required=approval_required,
                rollback_required=rollback_required,
                matched_dangerous_action=str(dangerous["id"]),
                reason="requested mode is below the minimum safe execution mode",
            )
        if approval_required and not approved:
            return AutonomyDecision(
                action_id=str(dangerous["id"]),
                mode=mode,
                allowed=False,
                approval_required=True,
                rollback_required=rollback_required,
                matched_dangerous_action=str(dangerous["id"]),
                reason="explicit human approval is required",
            )
        return AutonomyDecision(
            action_id=str(dangerous["id"]),
            mode=mode,
            allowed=True,
            approval_required=approval_required,
            rollback_required=rollback_required,
            matched_dangerous_action=str(dangerous["id"]),
            reason="dangerous action is approval-gated and approved",
        )

    mutable_modes = {"mode_3_approval_gated_execution", "mode_4_limited_autopilot"}
    allowed = mode in mutable_modes if any(word in proposed_action.lower() for word in ("apply", "publish", "deploy", "change", "send")) else True
    return AutonomyDecision(
        action_id="standard_action",
        mode=mode,
        allowed=allowed,
        approval_required=not allowed,
        rollback_required=False,
        matched_dangerous_action=None,
        reason="standard action is allowed" if allowed else "mutation-like action requires an execution mode",
    )
