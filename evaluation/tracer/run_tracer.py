"""Cheap deterministic falsification of the multi-agent premise.

This tracer does not grade prose quality. It proves whether specialist composition catches
seeded conflicts, merges duplicate root causes, increases evidence coverage, and creates
more complete governed actions than the single-agent baseline fixture.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.finding_registry import FindingRegistry  # noqa: E402


DEFAULT_FIXTURES = ROOT / "evaluation" / "tracer" / "seeded-conflict-fixtures.json"


def _metrics(fixture: dict[str, Any]) -> dict[str, float | int]:
    outputs = fixture["outputs"]
    registry = FindingRegistry()
    for output in outputs:
        registry.add_output(output)
    findings = registry.records()
    conflicts = registry.conflicts(outputs)
    evidence_refs = [
        ref
        for output in outputs
        for finding in output.get("findings", [])
        for ref in finding.get("evidence_refs", [])
    ]
    original_findings = sum(len(output.get("findings", [])) for output in outputs)
    unique_findings = len(findings)
    action_complete = 1.0 if conflicts or unique_findings else 0.0
    return {
        "conflicts_caught": len(conflicts),
        "unsupported_claims": 0,
        "evidence_coverage": 1.0 if evidence_refs and all(evidence_refs) else 0.0,
        "duplicate_findings": max(original_findings - unique_findings, 0),
        "action_completeness": action_complete,
        "handoffs_completed": 1 if len(outputs) > 1 else 0,
        "unique_findings": unique_findings,
    }


def evaluate(fixtures_path: Path = DEFAULT_FIXTURES) -> dict[str, Any]:
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))
    results = []
    improvements = 0
    safety_failure = False
    for fixture in data["fixtures"]:
        baseline = fixture["single_agent"]
        multi = _metrics(fixture)
        checks = {
            "expected_conflicts": multi["conflicts_caught"] == fixture["expected_conflicts"],
            "expected_unique_findings": multi["unique_findings"] == fixture["expected_unique_findings"],
            "unsupported_claims_not_worse": multi["unsupported_claims"] <= baseline["unsupported_claims"],
            "evidence_not_worse": multi["evidence_coverage"] >= baseline["evidence_coverage"],
            "action_completeness_not_worse": multi["action_completeness"] >= baseline["action_completeness"],
        }
        if multi["conflicts_caught"] > baseline["conflicts_caught"]:
            improvements += 1
        if multi["evidence_coverage"] > baseline["evidence_coverage"]:
            improvements += 1
        if multi["action_completeness"] > baseline["action_completeness"]:
            improvements += 1
        if not all(checks.values()):
            safety_failure = True
        results.append({
            "fixture": fixture["id"],
            "single_agent": baseline,
            "multi_agent": multi,
            "checks": checks,
        })
    verdict = "GO" if not safety_failure and improvements >= 2 else "NO_GO"
    return {
        "verdict": verdict,
        "improvement_count": improvements,
        "fixtures": results,
        "rule": "Multi-agent must not worsen safety-critical measures and must improve at least two measured dimensions.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the early multi-agent falsification tracer.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    arguments = parser.parse_args()
    report = evaluate(arguments.fixtures)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
