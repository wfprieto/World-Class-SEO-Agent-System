"""Immutable remediation program contracts and evidence hashes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "evaluation" / "remediation" / "owner-controlled-remediation-program.json"
SCHEMA_PATH = ROOT / "schemas" / "remediation-program.schema.json"
PHASE_IDS = [f"P{index}" for index in range(9)]
COMPLETION_GATES: dict[str, str | set[str]] = {
    "implementation_audit": "PASS",
    "focused_tests": "PASS",
    "full_certification": "PASS",
    "documentation": {"PASS", "NOT_APPLICABLE"},
    "learning": {"PASS", "NO_MATERIAL_LEARNING"},
    "unexpected_change_scan": "PASS",
}
EXCLUDED_PHRASES = {
    "public packaging and release maturity",
    "real-world SEO effectiveness and external reproduction",
}
GATE_EVIDENCE_CLASSES: dict[str, set[str]] = {
    "implementation_audit": {"SOURCE", "AUTOMATED"},
    "focused_tests": {"AUTOMATED"},
    "full_certification": {"CI"},
    "security_review": {"SOURCE", "AUTOMATED", "CI"},
    "documentation": {"SOURCE"},
    "learning": {"SOURCE", "AUTOMATED"},
    "unexpected_change_scan": {"AUTOMATED", "CI"},
}
CI_RUN_PATTERN = re.compile(
    r"^https://github\.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/[1-9][0-9]*$"
)
REQUIRED_CI_JOBS: dict[str, set[str]] = {
    "package certification": {
        "validate",
        "quality_security_release",
        "repository-certification",
        "phase0-rollback-certification",
    },
    "gate full_certification": {"validate", "quality_security_release", "repository-certification"},
    "gate security_review": {"quality_security_release"},
    "gate unexpected_change_scan": {"validate", "repository-certification"},
}


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def _schema_errors(program: dict[str, Any], schema: dict[str, Any], root: Path) -> list[str]:
    Draft202012Validator.check_schema(schema)
    reviewer_schema = _load_object(root / "schemas" / "reviewer-verdict.schema.json")
    Draft202012Validator.check_schema(reviewer_schema)
    registry: Registry[Any] = Registry().with_resources(
        [
            (str(schema["$id"]), Resource.from_contents(schema)),
            (str(reviewer_schema["$id"]), Resource.from_contents(reviewer_schema)),
        ]
    )
    validator = Draft202012Validator(schema, registry=registry)
    return [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(program), key=lambda item: list(item.absolute_path)
        )
    ]


def _gate_passes(actual: str, required: str | set[str]) -> bool:
    return actual in required if isinstance(required, set) else actual == required


def canonical_text_digest(content: bytes) -> str:
    """Hash repository text independently of Git checkout line-ending policy."""
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def evidence_package_hash(program: dict[str, Any], phase: dict[str, Any]) -> str:
    """Hash the immutable phase evidence reviewed independently of verdict storage."""

    def phase_contract(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in item.items()
            if key
            not in {
                "status",
                "review",
                "review_snapshot_commit",
                "frozen_package_commit",
                "package_certification",
            }
        }

    payload = {
        "schema_version": program.get("schema_version"),
        "program_id": program.get("program_id"),
        "objective": program.get("objective"),
        "baseline": program.get("baseline"),
        "apivr_tier": program.get("apivr_tier"),
        "direct_merge_permitted": program.get("direct_merge_permitted"),
        "scope": program.get("scope"),
        "exclusions": program.get("exclusions"),
        "evidence_classes": program.get("evidence_classes"),
        "phase_contracts": [phase_contract(item) for item in program.get("phases", [])],
        "phase_id": phase.get("id"),
        "authority_evidence": phase.get("authority_evidence", []),
        "audit_findings": program.get("audit_findings", []),
        "failures": [
            item for item in program.get("failures", []) if item.get("phase_id") == phase.get("id")
        ],
        "learning_records": [
            item
            for item in program.get("learning_records", [])
            if item.get("phase_id") == phase.get("id")
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
