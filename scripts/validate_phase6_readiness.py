from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, TypeGuard

if __package__:
    from scripts import autonomous_seo_review_trust as trust
    from scripts.publication_policy import REQUIRED_GATES as REQUIRED_GATES
    from scripts.publication_policy import REVIEWERS as REVIEWERS
    from scripts.publication_policy import required_gate_values
else:
    import autonomous_seo_review_trust as trust  # type: ignore[no-redef]
    from publication_policy import REQUIRED_GATES as REQUIRED_GATES
    from publication_policy import REVIEWERS as REVIEWERS
    from publication_policy import required_gate_values

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "docs/INSTALL.md", "docs/QUICKSTART.md", "docs/ARCHITECTURE.md",
    "docs/BENCHMARKS.md", "docs/GOVERNANCE.md", "docs/ROADMAP.md",
    "docs/TROUBLESHOOTING.md", "docs/SECURITY-MODEL.md",
    "CONTRIBUTORS.md", "CITATION.cff", ".github/CODEOWNERS",
    "evaluation/comparative/benchmark-cases.json",
    "evaluation/comparative/final-release-readiness.json",
    "evaluation/reviewers/final-scrummaster-3-verdict.json",
    "evaluation/reviewers/final-vp-engineering-verdict.json",
]


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"release evidence must contain an object: {path.name}")
    return payload


def _readiness_errors(data: dict[str, Any], root: Path) -> list[str]:
    failures: list[str] = []
    if data.get("release_decision") not in {"APPROVED", "BLOCKED"}:
        failures.append("release_decision must be APPROVED or BLOCKED")
    gates = data.get("gates")
    if not isinstance(gates, dict):
        return [*failures, "release gates must be an object containing every canonical gate"]
    missing = REQUIRED_GATES - set(gates)
    if missing:
        failures.append(f"missing required release gates: {sorted(missing)}")
    if data.get("release_decision") == "APPROVED":
        expected = required_gate_values()
        if gates != expected:
            failures.append("APPROVED release contains an unresolved or noncanonical gate")
        failures.extend(_approved_evidence_errors(data, root))
    return failures


def _approved_evidence_errors(data: dict[str, Any], root: Path) -> list[str]:
    failures: list[str] = []
    expected_states = dict.fromkeys(("code_verified", "live_verified", "externally_reproduced"), "PASS")
    if data.get("verification_state") != expected_states:
        failures.append("APPROVED release verification evidence is incomplete")
    target = data.get("evaluated_target_commit")
    if not isinstance(target, str) or re.fullmatch(r"[0-9a-f]{40}", target) is None:
        return [*failures, "APPROVED release requires an exact evaluated target commit"]
    if not _ci_evidence_matches_target(data.get("verified_ci"), target):
        failures.append("APPROVED release verification CI evidence is missing or not candidate-bound")
    for gate, (filename, reviewer) in REVIEWERS.items():
        verdict = _load(root / "evaluation/reviewers" / filename)
        if verdict.get("reviewer") != reviewer or verdict.get("verdict") != "APPROVE_GREAT":
            failures.append(f"APPROVED release reviewer evidence disagrees with {gate}")
        if verdict.get("candidate_commit") != target:
            failures.append(f"APPROVED release reviewer evidence is not candidate-bound: {gate}")
    benchmark = _load(root / "evaluation/comparative/benchmark-cases.json")
    if benchmark.get("execution_state") != "PASS":
        failures.append("APPROVED release benchmark verification evidence has not passed")
    failures.extend(_external_evidence_errors(data.get("verification_evidence"), root, target))
    return failures


def _ci_evidence_matches_target(ci: Any, target: str) -> bool:
    if not isinstance(ci, dict):
        return False
    run_id, cells = ci.get("run_id"), ci.get("cells")
    return (ci.get("commit") == target and ci.get("provider") == "GitHub Actions"
            and isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0
            and isinstance(cells, list) and bool(cells) and all(isinstance(cell, str) for cell in cells))


def _external_evidence_errors(evidence: Any, root: Path, target: str) -> list[str]:
    required = {"live_authorized_smokes", "external_reproduction"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        return ["APPROVED release verification_evidence must cover live smokes and external reproduction"]
    failures: list[str] = []
    for gate, block in evidence.items():
        if (not isinstance(block, dict) or block.get("state") != "PASS"
                or block.get("candidate_commit") != target):
            failures.append(f"verification_evidence {gate} is not PASS and candidate-bound")
            continue
        refs = block.get("evidence_refs")
        if not _valid_evidence_refs(refs):
            failures.append(f"verification_evidence {gate} requires nonempty structured evidence_refs")
            continue
        failures.extend(trust.candidate_evidence_ref_errors(refs, root, target))
    return failures


def _valid_evidence_refs(refs: Any) -> TypeGuard[list[dict[str, Any]]]:
    if not isinstance(refs, list) or not refs:
        return False
    return all(isinstance(ref, dict) and set(ref) == {"kind", "path", "sha256", "bound_commit"}
               and ref["kind"] == "repository_file"
               and all(isinstance(value, str) for value in ref.values()) for ref in refs)


def validate(*, require_approved: bool = False, root: Path = ROOT) -> list[str]:
    failures = [f"missing required Phase 6 artifact: {path}" for path in REQUIRED if not (root / path).is_file()]
    if require_approved:
        failures.append(
            "release publication requires authenticated detached completion evidence; "
            "local readiness labels cannot authorize publication"
        )
    readiness_path = root / "evaluation/comparative/final-release-readiness.json"
    if readiness_path.is_file():
        try:
            data = _load(readiness_path)
            failures.extend(_readiness_errors(data, root))
            if require_approved and data.get("release_decision") != "APPROVED":
                failures.append("release publication requires release_decision APPROVED")
        except (OSError, ValueError, TypeError) as exc:
            failures.append(f"invalid release evidence: {exc}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="Fail unless the release decision is APPROVED and every gate is resolved.",
    )
    arguments = parser.parse_args()
    failures = validate(require_approved=arguments.require_approved)
    if failures:
        print("Phase 6 readiness validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 6 readiness artifacts are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
