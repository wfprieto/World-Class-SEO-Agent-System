"""Closure-evidence validation for the autonomous SEO expansion program."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CLOSURE_SCHEMA_PATH = ROOT / "schemas" / "autonomous-seo-phase-closure.schema.json"
REVIEWER_SCHEMA_PATH = ROOT / "schemas" / "reviewer-verdict.schema.json"
REQUIRED_OUTCOME_PASS_PHASES = {"P12", "P13"}
REQUIRED_REVIEWERS = {
    "senior-scrummaster-3": "SENIOR_SCRUMMASTER_3",
    "vp-engineering": "VP_ENGINEERING",
}


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def schema_errors(
    payload: dict[str, Any], schema: dict[str, Any], label: str = "schema"
) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    return [
        f"{label} {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def git_stdout(root: Path, arguments: list[str]) -> str | None:
    result = _run_git(root, arguments)
    if result is None:
        return None
    value = result.stdout.strip()
    return value or None


def git_command_ok(root: Path, arguments: list[str]) -> bool:
    return _run_git(root, arguments) is not None


def _run_git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str] | None:
    if not (root / ".git").exists():
        return None
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def safe_repo_path(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def reviewer_file_errors(
    closure: dict[str, Any], root: Path, reviewer_schema: dict[str, Any]
) -> list[str]:
    verdicts: list[dict[str, Any]] = []
    errors: list[str] = []
    for relative in closure.get("reviewer_verdict_files", []):
        path = safe_repo_path(root, str(relative))
        if path is None or not path.is_file():
            errors.append(f"reviewer verdict file is missing or unsafe: {relative}")
            continue
        verdict = load_object(path)
        errors.extend(schema_errors(verdict, reviewer_schema, f"reviewer {relative}"))
        verdicts.append(verdict)
    if errors:
        return errors
    return reviewer_independence_errors(closure, verdicts)


def reviewer_independence_errors(
    closure: dict[str, Any], verdicts: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    if len(verdicts) != 2:
        return ["phase closure requires exactly two reviewer verdicts"]
    ids = {str(item.get("reviewer_id")): str(item.get("role")) for item in verdicts}
    if ids != REQUIRED_REVIEWERS:
        errors.append(f"phase closure reviewers must be {REQUIRED_REVIEWERS}; found {ids}")
    contexts = [str(item.get("context_id")) for item in verdicts]
    if len(set(contexts)) != 2 or closure.get("builder_context_id") in contexts:
        errors.append("reviewer contexts must be distinct and different from builder context")
    expected_hash = closure.get("evidence_package_hash")
    if any(item.get("evidence_package_hash") != expected_hash for item in verdicts):
        errors.append("both reviewers must review the exact phase evidence package hash")
    if any(item.get("verdict") != "APPROVE_GREAT" for item in verdicts):
        errors.append("both independent reviewers must return APPROVE_GREAT")
    return errors


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def closure_evidence_payload(closure: dict[str, Any]) -> dict[str, Any]:
    included = (
        "program_id",
        "phase_id",
        "candidate_commit",
        "builder_context_id",
        "apivr",
        "twenty_pass",
        "rollback",
        "technical_verification",
        "outcome_verification",
        "unexpected_change_scan",
        "security_review",
        "documentation_review",
        "evidence_refs",
    )
    return {key: closure[key] for key in included}


def closure_hash_errors(closure: dict[str, Any]) -> list[str]:
    expected = canonical_hash(closure_evidence_payload(closure))
    if closure.get("evidence_package_hash") == expected:
        return []
    return ["phase closure evidence_package_hash does not match its canonical evidence payload"]


def closure_path(root: Path, phase_id: str) -> Path:
    name = f"autonomous-seo-expansion-{phase_id.lower()}-closure.json"
    return root / "evaluation" / "remediation" / name


def phase_closure_errors(phase: dict[str, Any], root: Path) -> list[str]:
    phase_id = str(phase.get("id"))
    path = closure_path(root, phase_id)
    if not path.is_file():
        return [f"{phase_id} cannot be COMPLETE without {path.relative_to(root)}"]
    closure = load_object(path)
    errors = schema_errors(closure, load_object(CLOSURE_SCHEMA_PATH), f"{phase_id} closure")
    if errors:
        return errors
    errors.extend(closure_hash_errors(closure))
    errors.extend(_closure_identity_errors(phase, closure, root))
    errors.extend(reviewer_file_errors(closure, root, load_object(REVIEWER_SCHEMA_PATH)))
    return errors


def _closure_identity_errors(
    phase: dict[str, Any], closure: dict[str, Any], root: Path
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase.get("id"))
    candidate = str(closure.get("candidate_commit"))
    if closure.get("phase_id") != phase_id:
        errors.append(f"{phase_id} closure phase_id does not match")
    if (root / ".git").exists():
        errors.extend(_reviewed_candidate_errors(root, phase_id, candidate, closure))
    closure_outcome = closure.get("outcome_verification", {}).get("state")
    if phase_id in REQUIRED_OUTCOME_PASS_PHASES and closure_outcome != "PASS":
        errors.append(f"{phase_id} requires outcome_verification PASS before closure")
    return errors


def _reviewed_candidate_errors(
    root: Path, phase_id: str, candidate: str, closure: dict[str, Any]
) -> list[str]:
    if len(candidate) != 40:
        return [f"{phase_id} closure candidate_commit must be a 40-character SHA"]
    if not git_command_ok(root, ["merge-base", "--is-ancestor", candidate, "HEAD"]):
        return [f"{phase_id} closure candidate_commit must be an ancestor of final HEAD"]
    changed = git_stdout(root, ["diff", "--name-only", f"{candidate}..HEAD"])
    paths = [] if not changed else changed.splitlines()
    allowed = allowed_finalization_paths(phase_id, closure)
    unexpected = sorted(path for path in paths if path not in allowed)
    if unexpected:
        return [f"{phase_id} has post-review source drift outside closure evidence: {unexpected}"]
    return []


def allowed_finalization_paths(phase_id: str, closure: dict[str, Any]) -> set[str]:
    allowed = {
        "evaluation/remediation/autonomous-seo-expansion-program.json",
        "evaluation/remediation/autonomous-seo-expansion-ledger.md",
        f"evaluation/remediation/autonomous-seo-expansion-{phase_id.lower()}-closure.json",
    }
    allowed.update(str(item) for item in closure.get("reviewer_verdict_files", []))
    return allowed
