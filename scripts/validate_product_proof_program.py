"""Twenty-pass APIVR validation for the evidence-driven product rebuild."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(root: Path = ROOT) -> dict[str, Any]:
    rows: list[dict[str, Any]] = _json(
        root / "evaluation" / "product-proof" / "requirements.json"
    )["requirements"]
    failures: list[str] = []
    passes: list[dict[str, str]] = []

    def record(name: str, check: Callable[[], tuple[bool, str]]) -> None:
        ok, detail = check()
        passes.append(
            {
                "pass": str(len(passes) + 1),
                "name": name,
                "status": "PASS" if ok else "FAIL",
                "detail": detail,
            }
        )
        if not ok:
            failures.append(f"{name}: {detail}")

    ids = [str(row["id"]) for row in rows]
    record(
        "Requirement identity",
        lambda: (len(ids) == len(set(ids)), f"{len(ids)} unique requirements"),
    )
    record(
        "Source traceability",
        lambda: (
            all(row.get("source_sections") for row in rows),
            "Every requirement names report sections",
        ),
    )
    record(
        "Status vocabulary",
        lambda: (
            all(
                row["status"]
                in {
                    "IMPLEMENTED",
                    "PLANNED_NEXT_INCREMENT",
                    "BLOCKED_EXTERNAL_EVIDENCE",
                }
                for row in rows
            ),
            "No ambiguous completion state",
        ),
    )
    record(
        "Implemented artifacts",
        lambda: (
            all(
                all((root / path).exists() for path in row["implementation"])
                for row in rows
                if row["status"] == "IMPLEMENTED"
            ),
            "Every implemented requirement has existing artifacts",
        ),
    )
    record(
        "Implemented tests",
        lambda: (
            all(row.get("tests") for row in rows if row["status"] == "IMPLEMENTED"),
            "Every implemented requirement names tests",
        ),
    )
    record(
        "External blockers explicit",
        lambda: (
            all(row.get("blocker") for row in rows if row["status"] != "IMPLEMENTED"),
            "No deferred requirement is silently omitted",
        ),
    )

    checks: list[tuple[str, str]] = [
        ("Claim registry", "knowledge/seo-claim-registry.json"),
        ("Deprecation registry", "knowledge/deprecation-registry.json"),
        ("Primary source pack", "knowledge/primary-source-technical-seo.md"),
        ("Bounded crawler", "integrations/product_proof/crawler.py"),
        ("Rule engine", "integrations/product_proof/rules.py"),
        ("Root-cause reporting", "integrations/product_proof/report.py"),
        ("CLI product path", "seoctl/audit_cli.py"),
        ("Command overlay", "seoctl/command-registry-overlay.json"),
        ("Capability overlay", "orchestration/product-proof-capability-overlay.json"),
    ]
    for name, path in checks:
        record(name, lambda path=path: ((root / path).exists(), f"{path} exists"))

    service_text = (root / "integrations/product_proof/service.py").read_text(
        encoding="utf-8"
    )
    record(
        "Artifact manifest",
        lambda: ("run-manifest.json" in service_text, "Service writes a manifest"),
    )
    record(
        "Agent contribution ledger",
        lambda: (
            "agent-contributions.json" in service_text,
            "Contribution artifact is mandatory",
        ),
    )
    record(
        "Skill convergence",
        lambda: (
            (root / "skills/product-proof-technical-audit.md").exists()
            and (root / "skills/product-proof-procedures.md").exists(),
            "Skill and procedure extension exist",
        ),
    )
    record(
        "Feedback loops",
        lambda: (
            (root / "evaluation/product-proof/feedback-learning-loop.json").exists()
            and (
                root / "evaluation/product-proof/feedback-optimization-loop.json"
            ).exists(),
            "Learning and optimization records exist",
        ),
    )
    blocked = [
        str(row["id"])
        for row in rows
        if row["status"] == "BLOCKED_EXTERNAL_EVIDENCE"
    ]
    record(
        "Release truth",
        lambda: (
            bool(blocked),
            f"External proof remains blocked and explicit: {', '.join(blocked)}",
        ),
    )

    return {
        "status": "PASS" if not failures else "FAIL",
        "passes": passes,
        "failures": failures,
        "implemented": sum(row["status"] == "IMPLEMENTED" for row in rows),
        "planned_next_increment": sum(
            row["status"] == "PLANNED_NEXT_INCREMENT" for row in rows
        ),
        "blocked_external_evidence": sum(
            row["status"] == "BLOCKED_EXTERNAL_EVIDENCE" for row in rows
        ),
        "release_approved": False,
        "note": (
            "Implementation validation does not satisfy authorized live-site, "
            "external-review, CI-observability, or public-release gates."
        ),
    }


def main() -> int:
    result = validate(ROOT)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
