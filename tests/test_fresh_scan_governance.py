"""Controlled regressions for approval and executable-evidence trust boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_autonomous_seo_external_reviews as external_review
from scripts import autonomous_seo_program_closure as program_closure
from scripts import validate_autonomous_seo_expansion_program as expansion


def _write_json(root: Path, relative: str, payload: dict) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def test_quoted_rejection_is_not_approval(monkeypatch) -> None:
    receipt = {
        "reviewer_id": "senior-scrummaster-3",
        "result_actor_login": "claude[bot]",
        "repository_full_name": "wfprieto/World-Class-SEO-Agent-System",
        "pull_request_number": 38,
        "result_id": 101,
        "candidate_commit": "a" * 40,
        "canonical_ci_run_id": 201,
        "evidence_package_hash": "b" * 64,
    }
    verdict = {"verdict": "APPROVE_GREAT"}
    result = {
        "user": {"login": "claude[bot]"},
        "issue_url": "https://api.github.com/repos/wfprieto/World-Class-SEO-Agent-System/issues/38",
        "body": (
            f"> APPROVE_GREAT {receipt['candidate_commit']} 201 "
            f"{receipt['evidence_package_hash']}\nRejected: the quoted example is not approval."
        ),
    }
    monkeypatch.setattr(external_review, "_api_json", lambda *_: result)
    errors, _ = external_review._issue_comment_result(receipt, verdict, "synthetic")
    assert errors, "quoted approval tokens in a rejection must not authorize closure"

    result["body"] = json.dumps({
        "verdict": "APPROVE_GREAT",
        "candidate_commit": receipt["candidate_commit"],
        "canonical_ci_run_id": 201,
        "evidence_package_hash": receipt["evidence_package_hash"],
    })
    assert external_review._issue_comment_result(receipt, verdict, "synthetic")[0] == []
    decision = json.loads(result["body"])
    ambiguous = [
        json.dumps(result["body"]),
        json.dumps({**decision, "comment": "actually rejected"}),
        result["body"][:-1] + ', "verdict": "APPROVE_GREAT"}',
        json.dumps({key: value for key, value in decision.items() if key != "canonical_ci_run_id"}),
        json.dumps({**decision, "candidate_commit": "d" * 40}),
    ]
    for body in ambiguous:
        result["body"] = body
        assert external_review._issue_comment_result(receipt, verdict, "synthetic")[0]


@pytest.mark.parametrize("mode", ["FOUNDER_CONTROLLED", "INDEPENDENT_REVIEW"])
def test_terminal_reviews_are_authenticated_under_both_modes(tmp_path, monkeypatch, mode) -> None:
    _write_json(tmp_path, external_review.phase_closure.PROGRAM_RELATIVE, {
        "approval_model": mode, "program_evidence_state": "VERIFIED", "phases": [],
    })
    _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, {
        "candidate_commit": "a" * 40, "base_commit": "b" * 40,
        "canonical_ci_run_id": 201, "evidence_package_hash": "c" * 64,
        "reviewer_verdict_files": ["verdict-0.json", "verdict-1.json"],
        "reviewer_provenance_files": ["receipt-0.json", "receipt-1.json"],
    })
    for index, reviewer_id in enumerate(external_review.EXPECTED_MODELS):
        _write_json(tmp_path, f"verdict-{index}.json", {"reviewer_id": reviewer_id})
        _write_json(tmp_path, f"receipt-{index}.json", {
            "reviewer_id": reviewer_id, "execution_id": f"github:issue-comment:{index + 101}",
            "result_kind": "ISSUE_COMMENT", "result_id": index + 101,
            "trigger_comment_id": index + 201, "pull_request_number": 38,
        })
    calls = []
    monkeypatch.setattr(external_review, "_authenticate_one", lambda *args: calls.append(args) or [])
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic") == []
    assert len(calls) == 2, "final reviewers must be authenticated in both phase-approval modes"


def test_terminal_subject_rejects_candidate_replay() -> None:
    receipt = {
        "reviewer_id": "vp-engineering", "result_kind": "ISSUE_COMMENT", "result_id": 1,
        "execution_id": "github:issue-comment:1", "context_id": "github:issue-comment:1",
        "model": "github-codex-agent", "result_actor_login": "chatgpt-codex-connector[bot]",
        "candidate_commit": "a" * 40, "base_commit": "b" * 40,
        "canonical_ci_run_id": 201, "evidence_package_hash": "c" * 64,
    }
    expected = {**receipt, "candidate_commit": "d" * 40}
    errors = external_review._subject_errors(receipt, {"verdict": "APPROVE_GREAT"}, expected)
    assert any("candidate" in error for error in errors)


def test_terminal_schema_requires_explicit_base_and_ci() -> None:
    schema = json.loads((Path(__file__).parents[1] / "schemas/autonomous-seo-program-closure.schema.json").read_text())
    assert {"base_commit", "canonical_ci_run_id"} <= set(schema["required"])


def test_static_terminal_review_binding_rejects_base_and_run_replays(tmp_path) -> None:
    subject = {"candidate_commit": "a" * 40, "base_commit": "b" * 40,
               "canonical_ci_run_id": 201, "evidence_package_hash": "c" * 64,
               "reviewer_provenance_files": ["receipt.json"]}
    receipt = {key: subject[key] for key in (
        "candidate_commit", "base_commit", "canonical_ci_run_id", "evidence_package_hash",
    )}
    _write_json(tmp_path, "receipt.json", receipt)
    assert program_closure._review_subject_errors(subject, tmp_path) == []
    for field, wrong in (("base_commit", "d" * 40), ("canonical_ci_run_id", 202),
                         ("candidate_commit", "e" * 40), ("evidence_package_hash", "f" * 64)):
        _write_json(tmp_path, "receipt.json", {**receipt, field: wrong})
        assert any(field in error for error in program_closure._review_subject_errors(subject, tmp_path))


def test_legacy_founder_assertion_cannot_close_a_phase() -> None:
    root = Path(__file__).parents[1]
    program = json.loads((root / expansion.PROGRAM_PATH.relative_to(expansion.ROOT)).read_text())
    errors = expansion._founder_approval_errors(program["phases"][0], root, program)
    assert any("authenticated" in error or "legacy" in error for error in errors), (
        "a locally asserted founder identity without an observed owner act is not authorization"
    )


def test_founder_completion_authenticates_owner_act(tmp_path, monkeypatch) -> None:
    import shutil

    from tests.test_autonomous_seo_phase_closure_e2e import _prepare_candidate

    program, _, candidate, refs = _prepare_candidate(tmp_path)
    program["approval_model"] = "FOUNDER_CONTROLLED"
    program["phases"][0]["status"] = "COMPLETE"
    _write_json(tmp_path, external_review.phase_closure.PROGRAM_RELATIVE, program)
    schema = tmp_path / expansion.FOUNDER_APPROVAL_SCHEMA_RELATIVE
    shutil.copy2(expansion.ROOT / expansion.FOUNDER_APPROVAL_SCHEMA_RELATIVE, schema)
    relative = "evaluation/remediation/autonomous-seo-expansion-p0-founder-approval.json"
    approval = json.loads((expansion.ROOT / relative).read_text())
    approval.update({
        "schema_version": "1.1.0", "candidate_commit": candidate,
        "verification_evidence_refs": refs,
        "verification_evidence_hash": external_review.phase_closure.canonical_hash(refs),
        "owner_act": {"provider": "GITHUB_ISSUE_COMMENT",
                      "repository_full_name": "wfprieto/World-Class-SEO-Agent-System",
                      "pull_request_number": 38, "comment_id": 301},
    })
    _write_json(tmp_path, relative, approval)
    decision = {key: approval[key] for key in (
        "program_id", "phase_id", "candidate_commit", "verification_evidence_hash",
        "authorized_next_phase", "approval_state",
    )}
    event = {
        "id": 301, "user": {"login": "not-the-founder"},
        "issue_url": "https://api.github.com/repos/wfprieto/World-Class-SEO-Agent-System/issues/38",
        "created_at": "2026-09-06T12:00:00Z", "updated_at": "2026-09-06T12:00:00Z",
        "body": json.dumps(decision),
    }
    pr = {"number": 38, "head": {"sha": candidate}}
    monkeypatch.setattr(external_review, "_api_json", lambda path, _: event if "/comments/" in path else pr)
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), (
        "a local pointer does not authenticate an owner act"
    )
    event["user"]["login"] = "wfprieto"
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic") == []
    for field, wrong in (("phase_id", "P1"), ("candidate_commit", "f" * 40),
                         ("verification_evidence_hash", "0" * 64),
                         ("authorized_next_phase", "P2")):
        event["body"] = json.dumps({**decision, field: wrong})
        assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), field
    event["body"] = json.dumps(decision)
    program["phases"][0]["scope"].append("unapproved phase scope after owner candidate")
    _write_json(tmp_path, external_review.phase_closure.PROGRAM_RELATIVE, program)
    assert expansion._founder_approval_errors(program["phases"][0], tmp_path, program), (
        "owner approval cannot authenticate a changed phase definition"
    )


@pytest.mark.parametrize("mode", ["FOUNDER_CONTROLLED", "INDEPENDENT_REVIEW"])
def test_terminal_provider_observations_bind_all_subjects(tmp_path, monkeypatch, mode) -> None:
    from tests.test_autonomous_seo_phase_closure_e2e import _provenance, _reviewer

    subject = {"candidate_commit": "a" * 40, "base_commit": "b" * 40,
               "canonical_ci_run_id": 999, "evidence_package_hash": "c" * 64,
               "reviewer_verdict_files": [], "reviewer_provenance_files": []}
    observed = {}
    repository = "wfprieto/World-Class-SEO-Agent-System"
    observed[f"/repos/{repository}/pulls/37"] = {
        "number": 37, "head": {"sha": subject["candidate_commit"]},
        "base": {"sha": subject["base_commit"]},
    }
    run = {"head_sha": subject["candidate_commit"], "name": "Validate repository",
           "path": ".github/workflows/validate.yml", "event": "pull_request", "id": 999,
           "status": "completed", "conclusion": "success", "updated_at": "2026-08-11T15:00:00Z"}
    observed[f"/repos/{repository}/actions/runs/999"] = run
    for index, (reviewer_id, role) in enumerate(external_review.trust.REQUIRED_REVIEWERS.items()):
        actor = external_review.trust.EXPECTED_ACTORS[reviewer_id]
        provider = external_review.trust.EXPECTED_PROVIDERS[reviewer_id]
        model = external_review.EXPECTED_MODELS[reviewer_id]
        result_id, trigger_id = 101 + index, 201 + index
        context = f"github:issue-comment:{result_id}"
        receipt = _provenance(reviewer_id, role, context, provider, model, actor,
                              subject["base_commit"], subject["candidate_commit"],
                              subject["evidence_package_hash"], trigger_id, "ISSUE_COMMENT", result_id)
        verdict = _reviewer(reviewer_id, role, context, provider, model, subject["evidence_package_hash"])
        for key, payload, prefix in (("reviewer_verdict_files", verdict, "verdict"),
                                     ("reviewer_provenance_files", receipt, "receipt")):
            relative = f"{prefix}-{index}.json"
            subject[key].append(relative)
            _write_json(tmp_path, relative, payload)
        agent = "@claude" if index == 0 else "@codex"
        trigger = {"issue_url": f"https://api.github.com/repos/{repository}/issues/37",
                   "user": {"login": "wfprieto"}, "created_at": "2026-08-11T16:00:00Z",
                   "body": f"{agent} {subject['candidate_commit']} 999 {subject['evidence_package_hash']}"}
        observed[f"/repos/{repository}/issues/comments/{trigger_id}"] = trigger
        result = {"issue_url": trigger["issue_url"], "user": {"login": actor},
                  "created_at": verdict["submitted_at"], "body": json.dumps({
                      "verdict": "APPROVE_GREAT", "candidate_commit": subject["candidate_commit"],
                      "canonical_ci_run_id": 999, "evidence_package_hash": subject["evidence_package_hash"],
                  })}
        observed[f"/repos/{repository}/issues/comments/{result_id}"] = result
    _write_json(tmp_path, external_review.phase_closure.PROGRAM_RELATIVE, {
        "approval_model": mode, "program_evidence_state": "VERIFIED", "phases": [],
    })
    _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, subject)
    monkeypatch.setattr(external_review, "_api_json", lambda path, _: observed[path])
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic") == []
    for field, wrong in (("candidate_commit", "d" * 40), ("base_commit", "e" * 40),
                         ("canonical_ci_run_id", 998), ("evidence_package_hash", "f" * 64)):
        _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, {**subject, field: wrong})
        assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), field
    _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, subject)
    run["conclusion"] = "failure"
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic")
    run["conclusion"] = "success"
    _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, {**subject, "reviewer_provenance_files": []})
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), (
        "a terminal closure cannot omit both provider observations"
    )
    _write_json(tmp_path, program_closure.PROGRAM_CLOSURE_RELATIVE, subject)
    run["path"] = ".github/workflows/not-canonical.yml"
    assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), (
        "a same-named noncanonical workflow is not source-bound canonical CI"
    )
    run["path"] = ".github/workflows/validate.yml"
    pr = observed[f"/repos/{repository}/pulls/37"]
    for side in ("head", "base"):
        original = pr[side]["sha"]
        pr[side]["sha"] = "d" * 40
        assert external_review.validate_live_external_reviews(tmp_path, "synthetic"), side
        pr[side]["sha"] = original


def test_native_reviewer_approval_alternatives_remain_supported(monkeypatch) -> None:
    receipt = {"reviewer_id": "vp-engineering", "repository_full_name": "fixture/owned",
               "pull_request_number": 38, "trigger_comment_id": 201, "result_id": 101,
               "candidate_commit": "a" * 40,
               "result_actor_login": "chatgpt-codex-connector[bot]"}
    verdict = {"verdict": "APPROVE_GREAT"}
    result = {"user": {"login": receipt["result_actor_login"]},
              "commit_id": receipt["candidate_commit"], "state": "APPROVED"}
    monkeypatch.setattr(external_review, "_api_json", lambda *_: result)
    assert external_review._review_result(receipt, verdict, "synthetic")[0] == []
    result["state"] = "CHANGES_REQUESTED"
    assert external_review._review_result(receipt, verdict, "synthetic")[0]
    reaction = {"id": 101, "user": result["user"], "content": "+1"}
    monkeypatch.setattr(external_review, "_api_json", lambda *_: [reaction])
    assert external_review._reaction_result(receipt, verdict, "synthetic")[0] == []
    reaction["content"] = "-1"
    assert external_review._reaction_result(receipt, verdict, "synthetic")[0]
