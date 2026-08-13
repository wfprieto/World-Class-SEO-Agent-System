#!/usr/bin/env python3
"""Fail closed until private conduct intake has provider-verified evidence."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("governance/private-conduct-intake.json")
SCHEMA = Path("schemas/private-conduct-intake.schema.json")
BLOCKED_TEXT = "has not yet been designated"
OWNER_ACTION_TEXT = "OWNER_ACTION_REQUIRED"
REQUIRED_DISCLOSURES = {
    "acknowledgement target",
    "monitoring role",
    "confidentiality limits",
    "conflict handling",
}
PROHIBITED_EVIDENCE = {
    "repository issue comments",
    "repository commits",
    "self-authored assertions",
    "example or test destinations",
}
EXPECTED_PROHIBITED_DATA = {
    "credentials",
    "mailbox contents",
    "reporter identity",
    "report contents",
    "private access URLs",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _schema_errors(schema: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"schema {'.'.join(map(str, error.absolute_path)) or 'root'}: {error.message}"
        for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path))
    ]


def _operation_rows(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    operations = _load(root / "governance/repository-operations.json")
    remediation = _load(root / "governance/open-issue-remediation.json")
    operation: dict[str, Any] = next(
        (row for row in operations.get("critical_paths", []) if row.get("id") == "security-intake"),
        {},
    )
    issue: dict[str, Any] = next(
        (row for row in remediation.get("issues", []) if row.get("number") == 30), {}
    )
    return operation, issue


def _string_set(value: object) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return set(value)


def _activation_requirement_errors(contract: dict[str, Any]) -> list[str]:
    activation = contract.get("activation_requirements")
    if not isinstance(activation, dict):
        return ["private intake must declare provider-verification activation requirements"]
    errors: list[str] = []
    if activation.get("status") != "PROVIDER_VERIFICATION_REQUIRED":
        errors.append("private intake must remain gated on provider-verified evidence")
    if _string_set(activation.get("required_disclosures")) != REQUIRED_DISCLOSURES:
        errors.append("private intake must preserve every required public disclosure")
    if _string_set(activation.get("prohibited_evidence")) != PROHIBITED_EVIDENCE:
        errors.append("private intake must reject mutable, self-asserted, and test evidence")
    return errors


def _registry_errors(operation: dict[str, Any], issue: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if operation.get("status") != "BLOCKED_OWNER_ACTION":
        errors.append("security-intake must remain BLOCKED_OWNER_ACTION")
    if issue.get("state") != "BLOCKED_OWNER_ACTION":
        errors.append("issue 30 must remain BLOCKED_OWNER_ACTION")
    if operation.get("closure_evidence") != {
        "status": "PENDING_OWNER_ACTION",
        "refs": [],
    }:
        errors.append("blocked security-intake requires pending empty closure evidence")
    if not operation.get("blocker") or not issue.get("blocked_by"):
        errors.append("blocked private intake requires explicit owner blockers")
    return errors


def _documentation_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in ("SUPPORT.md", "CODE_OF_CONDUCT.md"):
        content = (root / relative).read_text(encoding="utf-8")
        normalized = " ".join(content.split())
        lowered = normalized.lower()
        if BLOCKED_TEXT not in normalized:
            errors.append(f"blocked intake status is not stated in {relative}")
        if OWNER_ACTION_TEXT not in content:
            errors.append(f"blocked intake owner action is not stated in {relative}")
        if "not a substitute for conduct reporting" not in lowered:
            errors.append(f"blocked intake must remain distinct from vulnerability intake in {relative}")
        for disclosure in REQUIRED_DISCLOSURES:
            if disclosure not in lowered:
                errors.append(f"future intake disclosure missing from {relative}: {disclosure}")
    return errors


def _blocked_contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("state") != "BLOCKED_OWNER_ACTION":
        errors.append("repository-only evidence cannot promote conduct intake to READY")
    if contract.get("destination") is not None:
        destination = json.dumps(contract.get("destination"), sort_keys=True).lower()
        if any(marker in destination for marker in ("example.", ".test", ".invalid", "localhost")):
            errors.append("example or test destinations cannot satisfy conduct intake")
        errors.append("BLOCKED_OWNER_ACTION requires a null destination")
    if any(
        contract.get(field) is not False
        for field in (
            "owner_authorized_publication",
            "repository_controlled",
            "distinct_from_security_intake",
        )
    ):
        errors.append("blocked intake must not claim owner authorization or destination verification")
    if contract.get("monitoring") != {
        "status": "PENDING_OWNER_ACTION",
        "monitor_role": None,
        "attested_at": None,
        "attestation_ref": None,
    }:
        errors.append("repository attestations cannot establish verified conduct monitoring")
    if contract.get("access_test") != {
        "status": "NOT_RUN",
        "tested_at": None,
        "method": None,
    }:
        errors.append("repository assertions cannot establish a provider access test")
    if contract.get("acknowledgement_target_hours") is not None:
        errors.append("blocked intake must not invent an acknowledgement target")
    return errors


def validate(root: Path = ROOT, *, as_of: date | None = None) -> list[str]:
    """Validate static blocked state; ``as_of`` is retained for caller compatibility."""
    del as_of
    try:
        contract = _load(root / CONTRACT)
        schema = _load(root / SCHEMA)
        operation, issue = _operation_rows(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    errors = _schema_errors(schema, contract)
    if _string_set(contract.get("prohibited_repository_data")) != EXPECTED_PROHIBITED_DATA:
        errors.append("private intake must preserve the exact prohibited repository-data set")
    errors.extend(_activation_requirement_errors(contract))
    errors.extend(_blocked_contract_errors(contract))
    errors.extend(_registry_errors(operation, issue))
    errors.extend(_documentation_errors(root))
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
