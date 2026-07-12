from __future__ import annotations

import json
from pathlib import Path

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


def validate() -> list[str]:
    failures = [f"missing required Phase 6 artifact: {path}" for path in REQUIRED if not (ROOT / path).is_file()]
    readiness_path = ROOT / "evaluation/comparative/final-release-readiness.json"
    if readiness_path.is_file():
        data = json.loads(readiness_path.read_text(encoding="utf-8"))
        if data.get("release_decision") not in {"APPROVED", "BLOCKED"}:
            failures.append("release_decision must be APPROVED or BLOCKED")
        gates = data.get("gates", {})
        if data.get("release_decision") == "APPROVED" and any(value != "PASS" and value != "APPROVE_GREAT" for value in gates.values()):
            failures.append("APPROVED release contains an unresolved gate")
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 6 readiness validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 6 readiness artifacts are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
