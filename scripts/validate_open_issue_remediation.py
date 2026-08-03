#!/usr/bin/env python3
"""Validate the six owner-approved open-issue remediation contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("governance/open-issue-remediation.json")
SCHEMA = Path("schemas/open-issue-remediation.schema.json")
EXPECTED = {
    26: ("architecture-quality-debt", "BOUNDED_DEBT"),
    28: ("network-provider-boundaries", "CODE_CAPABILITY"),
    29: ("documentation-knowledge-truth", "RECURRING_CONTROL"),
    30: ("security-intake", "OWNER_ACTION"),
    31: ("certification-supply-chain", "RECURRING_CONTROL"),
    32: ("runtime-evidence-integrity", "RECURRING_CONTROL"),
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _safe_file(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _schema_errors(schema: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    return [
        f"schema {'.'.join(map(str, error.absolute_path)) or 'root'}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(contract),
            key=lambda item: list(item.absolute_path),
        )
    ]


def _issue_index(rows: object) -> tuple[dict[int, dict[str, Any]], list[str]]:
    if not isinstance(rows, list):
        return {}, []
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = row.get("number")
        if isinstance(number, int) and not isinstance(number, bool):
            indexed[number] = row
    errors = []
    if set(indexed) != set(EXPECTED) or len(indexed) != len(rows):
        errors.append(
            "remediation contract must contain issues 26, 28, 29, 30, 31, and 32 exactly once"
        )
    return indexed, errors


def _issue_errors(
    number: int,
    row: dict[str, Any],
    operation_index: dict[str, dict[str, Any]],
    root: Path,
) -> list[str]:
    errors: list[str] = []
    control_id, classification = EXPECTED[number]
    if (row.get("control_id"), row.get("classification")) != (
        control_id,
        classification,
    ):
        errors.append(f"issue {number} classification does not match the canonical program")
    operation = operation_index.get(control_id, {})
    issue = operation.get("issue", {})
    if issue.get("number") != number:
        errors.append(f"issue {number} is not bound by repository operations")
    for relative in row.get("evidence_paths", []):
        if not isinstance(relative, str) or _safe_file(root, relative) is None:
            errors.append(f"issue {number} evidence path is missing or unsafe: {relative}")
    return errors


def _owner_blocker_errors(
    indexed: dict[int, dict[str, Any]], operation_index: dict[str, dict[str, Any]]
) -> list[str]:
    owner_row = indexed.get(30, {})
    security = operation_index.get("security-intake", {})
    if owner_row.get("state") == "BLOCKED_OWNER_ACTION":
        return (
            ["issue 30 blocker must agree with repository operations"]
            if security.get("status") != "BLOCKED_OWNER_ACTION"
            else []
        )
    return (
        ["issue 30 cannot claim remediation while repository operations remain blocked"]
        if security.get("status") == "BLOCKED_OWNER_ACTION"
        else []
    )


def validate(root: Path = ROOT) -> list[str]:
    try:
        contract = _load(root / CONTRACT)
        schema = _load(root / SCHEMA)
        operations = _load(root / "governance/repository-operations.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    errors = _schema_errors(schema, contract)
    rows = contract.get("issues")
    if not isinstance(rows, list):
        return errors
    indexed, index_errors = _issue_index(rows)
    errors.extend(index_errors)
    operation_index: dict[str, dict[str, Any]] = {}
    for row in operations.get("critical_paths", []):
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        if isinstance(identifier, str):
            operation_index[identifier] = row
    for number in EXPECTED:
        row = indexed.get(number)
        if isinstance(row, dict):
            errors.extend(_issue_errors(number, row, operation_index, root))
    errors.extend(_owner_blocker_errors(indexed, operation_index))
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
