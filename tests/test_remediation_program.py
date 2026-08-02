from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import urllib.error
from pathlib import Path

from scripts.validate_remediation_program import (
    PROGRAM_PATH,
    ROOT,
    SCHEMA_PATH,
    evidence_package_hash,
    canonical_text_digest,
    _closure_delta_errors,
    _evidence_errors,
    _rollback_evidence_errors,
    _validate_complete_phase,
    validate,
)
from scripts.validate_pytest_temp_isolation import validate as validate_temp_isolation


def _program() -> dict:
    return json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    fixture_payload = copy.deepcopy(payload)
    for finding in fixture_payload["audit_findings"]:
        finding["source_refs"] = ["schemas/remediation-program.schema.json"]
    for phase in fixture_payload["phases"]:
        verdicts = phase.get("review", {}).get("verdicts", [])
        if verdicts:
            package_hash = evidence_package_hash(fixture_payload, phase)
            phase["review"]["evidence_package_hash"] = package_hash
            for verdict in verdicts:
                verdict["evidence_package_hash"] = package_hash
    program_path = tmp_path / PROGRAM_PATH.relative_to(ROOT)
    schema_path = tmp_path / SCHEMA_PATH.relative_to(ROOT)
    program_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    program_path.write_text(json.dumps(fixture_payload, indent=2), encoding="utf-8")
    schema_path.write_bytes(SCHEMA_PATH.read_bytes())
    reviewer_path = tmp_path / "schemas" / "reviewer-verdict.schema.json"
    reviewer_path.write_text(
        (ROOT / "schemas" / "reviewer-verdict.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    reviewer_registry = tmp_path / "evaluation" / "reviewer-registry.json"
    reviewer_registry.parent.mkdir(parents=True, exist_ok=True)
    reviewer_registry.write_bytes((ROOT / "evaluation" / "reviewer-registry.json").read_bytes())
    reviewer_dir = tmp_path / "evaluation" / "reviewers"
    reviewer_dir.mkdir(parents=True, exist_ok=True)
    for name in ("senior-scrummaster-3.md", "vp-engineering.md"):
        (reviewer_dir / name).write_bytes((ROOT / "evaluation" / "reviewers" / name).read_bytes())
    rollback_bytes = (
        ROOT / "evaluation" / "remediation" / "phase0-rollback-evidence.json"
    ).read_bytes()
    for index in range(9):
        rollback_path = (
            tmp_path / "evaluation" / "remediation" / f"phase{index}-rollback-evidence.json"
        )
        rollback_path.write_bytes(rollback_bytes)
    return tmp_path


def _commit_fixture(root: Path, message: str) -> str:
    if not (root / ".git").exists():
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Remediation tests"],
            cwd=root,
            check=True,
        )
    subprocess.run(["git", "add", "--all"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _closure_payload(payload: dict, snapshot_commit: str) -> dict:
    closed = copy.deepcopy(payload)
    phase = closed["phases"][0]
    phase["status"] = "COMPLETE"
    phase["review_snapshot_commit"] = snapshot_commit
    phase["frozen_package_commit"] = snapshot_commit
    phase["package_certification"] = [{"closure-only": True}]
    phase["review"] = {"evidence_package_hash": "frozen", "verdicts": []}
    closed["current_phase"] = "P1"
    closed["phases"][1]["status"] = "IN_PROGRESS"
    return closed


def _complete_phase(payload: dict, phase_index: int) -> None:
    phase = payload["phases"][phase_index]
    phase["status"] = "COMPLETE"
    phase["verified_commit"] = payload["baseline"]["commit"]
    phase["review_snapshot_commit"] = phase["verified_commit"]
    phase["frozen_package_commit"] = phase["verified_commit"]
    phase["rollback_evidence_sha256"] = canonical_text_digest(
        (ROOT / "evaluation" / "remediation" / "phase0-rollback-evidence.json").read_bytes()
    )
    schema_digest = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    for criterion in phase["acceptance_criteria"]:
        criterion["status"] = "PASS"
        criterion["evidence_refs"] = [
            {
                "class": "AUTOMATED",
                "ref": "schemas/remediation-program.schema.json",
                "commit": phase["verified_commit"],
                "sha256": schema_digest,
                "environment": "LOCAL",
                "status": "PASS",
                "assertion": f"{criterion['id']} passed the isolated validator fixture.",
            }
        ]
    phase["acceptance_criteria"][0]["evidence_refs"].extend(
        [
            {
                "class": "SOURCE",
                "ref": "schemas/remediation-program.schema.json",
                "commit": phase["verified_commit"],
                "sha256": schema_digest,
                "environment": "LOCAL",
                "status": "OBSERVED",
                "assertion": "The frozen source schema was inspected.",
            },
            {
                "class": "CI",
                "ref": "https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/1",
                "commit": phase["verified_commit"],
                "sha256": None,
                "environment": "CI",
                "status": "PASS",
                "assertion": "The exact verified commit passed certification.",
                "provenance": _ci_provenance(phase["verified_commit"]),
            },
        ]
    )
    for evidence_class in phase["required_evidence_classes"]:
        if evidence_class in {"PROVIDER", "DEPLOYED", "OPERATIONAL"}:
            phase["acceptance_criteria"][0]["evidence_refs"].append(
                {
                    "class": evidence_class,
                    "ref": f"https://provider.example.invalid/{evidence_class.lower()}",
                    "commit": phase["verified_commit"],
                    "sha256": None,
                    "environment": evidence_class,
                    "status": "PASS",
                    "assertion": f"The required {evidence_class} state was observed.",
                }
            )
    phase["gates"] = {
        "implementation_audit": "PASS",
        "focused_tests": "PASS",
        "full_certification": "PASS",
        "security_review": "PASS",
        "documentation": "PASS",
        "learning": "NO_MATERIAL_LEARNING",
        "unexpected_change_scan": "PASS",
    }
    evidence_paths = {
        "implementation_audit": ("SOURCE", "schemas/remediation-program.schema.json"),
        "focused_tests": ("AUTOMATED", "schemas/remediation-program.schema.json"),
        "full_certification": (
            "CI",
            "https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/1",
        ),
        "security_review": ("SOURCE", "schemas/remediation-program.schema.json"),
        "documentation": ("SOURCE", "schemas/remediation-program.schema.json"),
        "learning": ("AUTOMATED", "schemas/remediation-program.schema.json"),
        "unexpected_change_scan": ("AUTOMATED", "schemas/remediation-program.schema.json"),
    }
    phase["gate_evidence"] = {}
    for gate, (evidence_class, reference) in evidence_paths.items():
        record = {
            "class": evidence_class,
            "ref": reference,
            "commit": phase["verified_commit"],
            "sha256": None if evidence_class == "CI" else schema_digest,
            "environment": "CI" if evidence_class in {"CI", "AUTOMATED"} else "LOCAL",
            "status": "PASS",
            "assertion": f"[{gate}] The exact verified commit passed this completion gate.",
        }
        if evidence_class == "CI":
            record["provenance"] = _ci_provenance(phase["verified_commit"])
        phase["gate_evidence"][gate] = [record]
    phase["evidence_status"] = {
        "SOURCE": "PASS",
        "AUTOMATED": "PASS",
        "CI": "PASS",
        "PROVIDER": "OUT_OF_SCOPE",
        "DEPLOYED": "OUT_OF_SCOPE",
        "OPERATIONAL": "OUT_OF_SCOPE",
    }
    for evidence_class in phase["required_evidence_classes"]:
        phase["evidence_status"][evidence_class] = "PASS"
    for finding in payload["audit_findings"]:
        if finding["phase_id"] == phase["id"]:
            finding["status"] = "RESOLVED"
    authority_paths = [
        "evaluation/reviewer-registry.json",
        "schemas/reviewer-verdict.schema.json",
        "evaluation/reviewers/senior-scrummaster-3.md",
        "evaluation/reviewers/vp-engineering.md",
    ]
    phase["authority_evidence"] = [
        {
            "class": "SOURCE",
            "ref": reference,
            "commit": phase["verified_commit"],
            "sha256": hashlib.sha256((ROOT / reference).read_bytes()).hexdigest(),
            "environment": "LOCAL",
            "status": "PASS",
            "assertion": "Reviewer authority is bound to immutable source content.",
        }
        for reference in authority_paths
    ]
    phase["package_certification"] = [
        {
            "class": "CI",
            "ref": "https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/1",
            "commit": phase["verified_commit"],
            "sha256": None,
            "environment": "CI",
            "status": "PASS",
            "assertion": "The frozen evidence package passed repository certification.",
            "provenance": _ci_provenance(phase["verified_commit"]),
        }
    ]
    _refresh_review(payload, phase)


def _ci_provenance(commit: str) -> dict:
    return {
        "repository": "wfprieto/World-Class-SEO-Agent-System",
        "workflow": "Validate repository",
        "head_sha": commit,
        "conclusion": "success",
        "jobs": ["repository-certification"],
    }


def _schema_evidence(
    commit: str, *, assertion: str = "The immutable schema verifies this record."
) -> dict:
    return {
        "class": "AUTOMATED",
        "ref": "schemas/remediation-program.schema.json",
        "commit": commit,
        "sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
        "environment": "LOCAL",
        "status": "PASS",
        "assertion": assertion,
    }


def _verdict(phase_id: str, role: str, reviewer: str, package_hash: str) -> dict:
    return {
        "review_id": f"review-{phase_id.lower()}-{reviewer}",
        "reviewer_id": "senior-scrummaster-3"
        if role == "SENIOR_SCRUMMASTER_3"
        else "vp-engineering",
        "role": role,
        "context_id": f"context-{reviewer}-{phase_id.lower()}-fresh",
        "provider": "test-provider",
        "model": "test-model",
        "evidence_package_hash": package_hash,
        "verdict": "APPROVE_GREAT",
        "strongest_objections": [
            "The exact commit must stay immutable.",
            "The rollback path must stay executable.",
            "The evidence must remain independently reproducible.",
        ],
        "evidence_refs": ["test-evidence-package"],
        "residual_risks": [],
        "required_changes": [],
        "submitted_at": "2026-08-01T00:00:00Z",
        "saw_other_reviewer_verdict": False,
        "is_builder": False,
    }


def _refresh_review(payload: dict, phase: dict) -> None:
    package_hash = evidence_package_hash(payload, phase)
    phase["review"] = {
        "evidence_package_hash": package_hash,
        "verdicts": [
            _verdict(phase["id"], "SENIOR_SCRUMMASTER_3", "scrum", package_hash),
            _verdict(phase["id"], "VP_ENGINEERING", "vpeng", package_hash),
        ],
    }


def test_current_remediation_program_is_valid() -> None:
    assert validate() == []


def test_phase_skipping_is_rejected(tmp_path: Path) -> None:
    payload = _program()
    payload["current_phase"] = "P2"
    payload["phases"][0]["status"] = "NOT_STARTED"
    payload["phases"][2]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "P0 precedes current_phase and must be COMPLETE" in errors
    assert "P1 precedes current_phase and must be COMPLETE" in errors


def test_phase_completion_requires_every_gate_evidence_and_independent_review(
    tmp_path: Path,
) -> None:
    payload = _program()
    payload["phases"][0]["status"] = "COMPLETE"
    payload["phases"][0]["verified_commit"] = None
    for criterion in payload["phases"][0]["acceptance_criteria"]:
        criterion["status"] = "NOT_RUN"
        criterion["evidence_refs"] = []
    payload["phases"][0]["evidence_status"]["AUTOMATED"] = "NOT_RUN"
    payload["phases"][0]["evidence_status"]["CI"] = "NOT_RUN"
    payload["phases"][0]["gates"] = {key: "NOT_RUN" for key in payload["phases"][0]["gates"]}
    payload["phases"][0]["review"] = {"evidence_package_hash": None, "verdicts": []}
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("P0 cannot be COMPLETE: gate focused_tests is NOT_RUN" in item for item in errors)
    assert any("P0-AC-01 is not PASS" in item for item in errors)
    assert any("requires one canonical verdict from each" in item for item in errors)
    assert any("requires two APPROVE_GREAT" in item for item in errors)


def test_resolved_failure_requires_confirmed_recurrence_guardrail(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    payload["failures"] = [
        {
            "id": "FAIL-0001",
            "phase_id": "P0",
            "summary": "The production-path validator initially accepted a skipped phase.",
            "status": "RESOLVED",
            "evidence_refs": [_schema_evidence(payload["baseline"]["commit"])],
        }
    ]

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("resolved failure FAIL-0001 has no learning record" in item for item in errors)


def test_confirmed_learning_allows_resolved_failure_to_close(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    payload["failures"] = [
        {
            "id": "FAIL-0001",
            "phase_id": "P0",
            "summary": "The production-path validator initially accepted a skipped phase.",
            "status": "RESOLVED",
            "evidence_refs": [_schema_evidence(payload["baseline"]["commit"])],
        }
    ]
    payload["learning_records"] = [
        {
            "id": "LEARN-0001",
            "phase_id": "P0",
            "failure_id": "FAIL-0001",
            "status": "CONFIRMED",
            "affected_invariant": "Phases advance only in canonical order.",
            "expected_result": "The validator rejects every skipped predecessor phase.",
            "observed_evidence": [
                {
                    "class": "AUTOMATED",
                    "ref": "schemas/remediation-program.schema.json",
                    "commit": payload["baseline"]["commit"],
                    "sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
                    "environment": "LOCAL",
                    "status": "PASS",
                    "assertion": "The phase-skip regression is passing.",
                }
            ],
            "learning": "Phase ordering must be checked by the production validator.",
            "recurrence_signature": "A later phase starts while a predecessor is incomplete.",
            "guardrail": "Keep a child-fixture regression that skips P1.",
            "verification_evidence": _schema_evidence(payload["baseline"]["commit"]),
            "rollback_position": "Revert the validator and its schema together.",
            "residual_risk": "Manual artifacts outside this program remain advisory.",
            "owner": "Quality owner",
            "due_phase": "P0",
            "apivr_next_action": "Retain the regression in every certification run.",
        }
    ]
    _refresh_review(payload, payload["phases"][0])

    assert validate(_write_fixture(tmp_path, payload)) == []

    payload["learning_records"][0]["observed_evidence"][0]["sha256"] = "0" * 64
    payload["failures"][0]["evidence_refs"][0]["ref"] = "missing/failure-evidence.json"
    _refresh_review(payload, payload["phases"][0])
    errors = validate(_write_fixture(tmp_path / "forged", payload))
    assert any("learning LEARN-0001 evidence digest is not immutable" in item for item in errors)
    assert any("failure FAIL-0001 evidence does not exist" in item for item in errors)


def test_reviewer_contexts_must_be_distinct(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["phases"][0]["review"]["verdicts"][1]["context_id"] = payload["phases"][0]["review"][
        "verdicts"
    ][0]["context_id"]
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("requires distinct reviewer identities and contexts" in item for item in errors)


def test_exclusions_and_no_direct_merge_are_immutable(tmp_path: Path) -> None:
    payload = copy.deepcopy(_program())
    payload["exclusions"] = ["something else", "another exclusion"]
    payload["direct_merge_permitted"] = True

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("must preserve explicit exclusions" in item for item in errors)
    assert any("direct_merge_permitted" in item or "direct merge" in item for item in errors)


def test_excluded_evidence_classes_cannot_be_promoted(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["phases"][0]["evidence_status"]["PROVIDER"] = "PASS"
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any(
        "passing evidence class PROVIDER has no structured record" in item for item in errors
    )


def test_open_audit_finding_blocks_phase_completion(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["audit_findings"][0]["status"] = "OPEN"
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "P0 cannot be COMPLETE: audit finding AUD-001 is OPEN" in errors


def test_reviewer_context_cannot_be_reused_across_phases(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    _complete_phase(payload, 1)
    payload["phases"][1]["review"]["verdicts"][1]["context_id"] = payload["phases"][0]["review"][
        "verdicts"
    ][0]["context_id"]
    payload["current_phase"] = "P2"
    payload["phases"][2]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "reviewer contexts cannot be reused across phases or roles" in errors


def test_evidence_hash_binds_material_program_controls_and_full_audit_inventory() -> None:
    payload = _program()
    original = evidence_package_hash(payload, payload["phases"][0])
    mutations = []
    for field, value in (
        ("objective", "A materially different objective that remains long enough for the schema."),
        ("scope", [*payload["scope"], "new material scope"]),
        ("apivr_tier", "FORENSIC"),
        ("direct_merge_permitted", True),
    ):
        changed = copy.deepcopy(payload)
        changed[field] = value
        mutations.append(changed)
    changed_finding = copy.deepcopy(payload)
    changed_finding["audit_findings"][-1]["summary"] += " Mutated."
    mutations.append(changed_finding)

    assert all(evidence_package_hash(item, item["phases"][0]) != original for item in mutations)


def test_evidence_hash_survives_only_workflow_state_and_verdict_insertion() -> None:
    payload = _program()
    original = evidence_package_hash(payload, payload["phases"][0])
    payload["current_phase"] = "P1"
    payload["phases"][0]["status"] = "COMPLETE"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    payload["phases"][0]["review"] = {
        "evidence_package_hash": original,
        "verdicts": [],
    }
    payload["phases"][0]["review_snapshot_commit"] = payload["baseline"]["commit"]
    payload["phases"][0]["frozen_package_commit"] = payload["baseline"]["commit"]
    payload["phases"][0]["package_certification"] = []

    assert evidence_package_hash(payload, payload["phases"][0]) == original


def test_canonical_looking_nonexistent_ci_run_is_rejected_in_ci(monkeypatch) -> None:
    commit = "1" * 40
    evidence = {
        "class": "CI",
        "ref": "https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/999999999999",
        "commit": commit,
        "sha256": None,
        "environment": "CI",
        "status": "PASS",
        "assertion": "A forged but canonical-looking run must fail authentication.",
        "provenance": _ci_provenance(commit),
    }

    def fail_request(*args, **kwargs):
        raise urllib.error.URLError("not found")

    monkeypatch.setattr("urllib.request.urlopen", fail_request)

    errors = _evidence_errors(
        evidence,
        commit,
        ROOT,
        "P0 package certification",
        authenticate_ci=True,
    )

    assert any("could not be authenticated" in item for item in errors)


def test_unregistered_reviewer_identity_cannot_approve_phase(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["phases"][0]["review"]["verdicts"][0]["reviewer_id"] = "schema-valid-impostor"
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("not the canonical registered identity" in item for item in errors)


def test_reviewer_registry_is_hash_bound_and_worktree_mutation_cannot_reauthorize() -> None:
    payload = _program()
    _complete_phase(payload, 0)
    phase = payload["phases"][0]
    original = evidence_package_hash(payload, phase)
    phase["authority_evidence"][0]["sha256"] = "0" * 64

    assert evidence_package_hash(payload, phase) != original


def test_rollback_digest_is_checkout_line_ending_independent() -> None:
    assert canonical_text_digest(b"one\ntwo\n") == canonical_text_digest(b"one\r\ntwo\r\n")


def test_durable_rollback_procedure_rejects_stale_candidate_and_inventory() -> None:
    rollback_path = ROOT / "evaluation" / "remediation" / "phase0-rollback-evidence.json"
    rollback = json.loads(rollback_path.read_text(encoding="utf-8"))

    assert _rollback_evidence_errors(rollback, _program(), ROOT, "P0 rollback") == []

    rollback["candidate_selector"] = "verified_commit"
    rollback["commit_range"] = "baseline_commit..obsolete_candidate_commit"
    rollback["recovery_position"] = "Revert the nine recorded commits."
    rollback["candidate_commit"] = "7" * 40

    errors = _rollback_evidence_errors(rollback, _program(), ROOT, "P0 rollback")

    assert any("fields do not match" in item for item in errors)
    assert any("candidate_selector is stale or unsafe" in item for item in errors)
    assert any("commit_range is stale or unsafe" in item for item in errors)
    assert any("recovery_position is stale or unsafe" in item for item in errors)


def test_closure_delta_accepts_only_state_verdict_and_certification_fields(
    tmp_path: Path,
) -> None:
    root = _write_fixture(tmp_path, _program())
    snapshot_commit = _commit_fixture(root, "review snapshot")
    closed = _closure_payload(_program(), snapshot_commit)
    _write_fixture(root, closed)
    _commit_fixture(root, "phase closure")
    closed = json.loads((root / PROGRAM_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))

    assert _closure_delta_errors(closed, closed["phases"][0], root, snapshot_commit) == []


def test_closure_delta_rejects_material_program_and_unrelated_file_changes(
    tmp_path: Path,
) -> None:
    root = _write_fixture(tmp_path, _program())
    snapshot_commit = _commit_fixture(root, "review snapshot")
    closed = _closure_payload(_program(), snapshot_commit)
    closed["objective"] = "A material objective change hidden in the closure commit."
    _write_fixture(root, closed)
    (root / "unrelated.txt").write_text("not closure metadata", encoding="utf-8")
    _commit_fixture(root, "forged phase closure")
    closed = json.loads((root / PROGRAM_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))

    errors = _closure_delta_errors(closed, closed["phases"][0], root, snapshot_commit)

    assert "closure changes files outside the canonical remediation program" in errors
    assert "closure delta contains fields outside the status-and-verdict allowlist" in errors


def test_generic_or_unauthenticated_gate_evidence_is_rejected(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    generic = {
        "class": "CI",
        "ref": "https://example.invalid/runs/forged",
        "commit": payload["baseline"]["commit"],
        "sha256": None,
        "environment": "CI",
        "status": "PASS",
        "assertion": "A generic record allegedly passed every completion gate.",
    }
    payload["phases"][0]["gate_evidence"] = {
        gate: [copy.deepcopy(generic)] for gate in payload["phases"][0]["gates"]
    }
    _refresh_review(payload, payload["phases"][0])

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("not a canonical repository run" in item for item in errors)
    assert any("lacks a gate-specific assertion" in item for item in errors)
    assert any("rejects evidence class CI" in item for item in errors)


def test_pytest_temp_root_must_be_outside_repository_boundary(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    assert validate_temp_isolation(repository / "nested", repository_root=repository)
    assert validate_temp_isolation(tmp_path / "isolated", repository_root=repository) == []


def test_pytest_temp_root_must_be_outside_any_enclosing_git_worktree(tmp_path: Path) -> None:
    enclosing = tmp_path / "enclosing"
    enclosing.mkdir()
    subprocess.run(["git", "init", "--quiet", str(enclosing)], check=True)
    unrelated_repository = tmp_path / "repository"
    unrelated_repository.mkdir()

    errors = validate_temp_isolation(
        enclosing / "pytest" / "case", repository_root=unrelated_repository
    )

    assert any("enclosing Git worktree" in item for item in errors)


def test_phase_zero_requires_explicit_review_snapshot_before_closure() -> None:
    payload = _program()
    phase = payload["phases"][0]
    phase["status"] = "COMPLETE"
    phase["review_snapshot_commit"] = None
    phase["frozen_package_commit"] = None
    phase["package_certification"] = []
    _refresh_review(payload, phase)

    errors = _validate_complete_phase(phase, payload, ROOT)

    assert any("review_snapshot_commit is missing" in item for item in errors)
