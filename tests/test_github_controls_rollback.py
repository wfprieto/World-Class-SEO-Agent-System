from __future__ import annotations

import json
import datetime as dt
from pathlib import Path

import pytest

from scripts.plan_github_controls_rollback import (
    REPOSITORY,
    apply_plan,
    authorize_apply,
    build_plan,
    execute_verified_rollback,
    restored_state_errors,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / f"evaluation/remediation/{name}").read_text(encoding="utf-8"))


def _observed_from_baseline(baseline: dict, **overrides: object) -> dict:
    return {
        **baseline,
        "authenticated": True,
        "authenticated_actor": "test-owner",
        "capture_method": "gh-api-live",
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        **overrides,
    }


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


@pytest.mark.parametrize(
    ("repository", "allow", "authorization", "message"),
    [
        ("attacker/wrong", True, "YES", "repository confirmation"),
        (REPOSITORY, False, "YES", "allow-security-downgrade"),
        (REPOSITORY, True, "NO", "incident authorization"),
    ],
)
def test_every_apply_authorization_gate_fails_closed(
    repository: str, allow: bool, authorization: str, message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        authorize_apply(
            confirm_repository=repository,
            allow_security_downgrade=allow,
            authorization=authorization,
        )


def test_apply_uses_exact_endpoint_methods_and_payloads() -> None:
    baseline = _load("phase1-provider-baseline.json")
    current = _load("phase1-provider-evidence.json")
    current["secret_scanning"] = False
    current["secret_scanning_push_protection"] = False
    plan = build_plan(baseline, current)
    calls: list[tuple[str, str, dict | None]] = []

    def fake_gh(method: str, endpoint: str, payload: dict | None = None) -> None:
        calls.append((method, endpoint, payload))

    applied = apply_plan(plan, baseline, gh_call=fake_gh)
    assert applied == [change["setting"] for change in plan["changes"]]
    assert ("DELETE", f"repos/{REPOSITORY}/private-vulnerability-reporting", None) in calls
    assert ("PATCH", f"repos/{REPOSITORY}", {"has_discussions": False}) in calls
    assert ("DELETE", f"repos/{REPOSITORY}/vulnerability-alerts", None) in calls
    assert ("DELETE", f"repos/{REPOSITORY}/automated-security-fixes", None) in calls
    assert (
        "PATCH",
        f"repos/{REPOSITORY}",
        {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}},
    ) in calls
    assert (
        "PATCH",
        f"repos/{REPOSITORY}",
        {
            "security_and_analysis": {
                "secret_scanning_push_protection": {"status": "enabled"}
            }
        },
    ) in calls
    ruleset_call = next(call for call in calls if call[1].endswith("/rulesets/18955880"))
    assert ruleset_call[0] == "PUT"
    assert ruleset_call[2]["rules"][2]["parameters"]["required_approving_review_count"] == 0


def test_partial_provider_failure_is_truthfully_sealed() -> None:
    baseline = _load("phase1-provider-baseline.json")
    plan = build_plan(baseline, _load("phase1-provider-evidence.json"))
    calls = 0

    def failing_gh(method: str, endpoint: str, payload: dict | None = None) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected provider failure")

    receipt = execute_verified_rollback(
        plan,
        baseline,
        gh_call=failing_gh,
        capture_call=lambda: pytest.fail("capture must not run after partial failure"),
    )
    assert receipt["result"] == "FAIL_PARTIAL_APPLICATION"
    assert receipt["applied_settings"] == [plan["changes"][0]["setting"]]
    assert "injected provider failure" in receipt["errors"][0]


def test_post_restore_mismatch_fails_closed() -> None:
    baseline = _load("phase1-provider-baseline.json")
    observed = _observed_from_baseline(baseline, discussions=True)
    errors = restored_state_errors(baseline, observed)
    assert errors == ["post-restore discussions does not match baseline"]
    receipt = execute_verified_rollback(
        {"changes": []},
        baseline,
        gh_call=lambda *_args, **_kwargs: None,
        capture_call=lambda: observed,
    )
    assert receipt["result"] == "FAIL_POST_RESTORE_MISMATCH"


def test_successful_apply_requires_fresh_authenticated_exact_match() -> None:
    baseline = _load("phase1-provider-baseline.json")
    observed = _observed_from_baseline(baseline)
    plan = build_plan(baseline, _load("phase1-provider-evidence.json"))
    calls: list[tuple[str, str, dict | None]] = []
    receipt = execute_verified_rollback(
        plan,
        baseline,
        gh_call=lambda method, endpoint, payload=None: calls.append(
            (method, endpoint, payload)
        ),
        capture_call=lambda: observed,
    )
    assert receipt["result"] == "PASS"
    assert receipt["applied_settings"] == [
        change["setting"] for change in plan["changes"]
    ]
    assert len(calls) == len(plan["changes"])
    assert receipt["post_restore_capture"]["captured_at"] == observed["captured_at"]
    assert receipt["errors"] == []


def test_stale_or_failed_post_restore_capture_cannot_pass() -> None:
    baseline = _load("phase1-provider-baseline.json")
    stale = _observed_from_baseline(baseline, captured_at="2000-01-01T00:00:00Z")
    assert any("five-minute" in error for error in restored_state_errors(baseline, stale))
    receipt = execute_verified_rollback(
        {"changes": []},
        baseline,
        gh_call=lambda *_args, **_kwargs: None,
        capture_call=lambda: (_ for _ in ()).throw(RuntimeError("capture unavailable")),
    )
    assert receipt["result"] == "FAIL_POST_RESTORE_CAPTURE"
    assert "capture unavailable" in receipt["errors"][0]
