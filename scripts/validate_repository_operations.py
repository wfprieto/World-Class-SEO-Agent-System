#!/usr/bin/env python3
"""Validate the bounded, static repository-operations contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("governance/repository-operations.json")
SCHEMA_PATH = Path("schemas/repository-operations.schema.json")
REPOSITORY = "wfprieto/World-Class-SEO-Agent-System"
EXPECTED_ISSUES = {
    "security-intake": 30,
    "repository-governance": 27,
    "certification-supply-chain": 31,
    "runtime-evidence-integrity": 32,
    "network-provider-boundaries": 28,
    "documentation-knowledge-truth": 29,
    "architecture-quality-debt": 26,
}
OWNER_ACTION_PATHS = {
    "repository-governance",
    "security-intake",
}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _heading_anchors(markdown: str) -> set[str]:
    anchors = set(re.findall(r'<a\s+id=["\']([a-z0-9-]+)["\']\s*></a>', markdown))
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", markdown, flags=re.MULTILINE):
        anchor = heading.strip().lower()
        anchor = re.sub(r"[^a-z0-9 _-]", "", anchor)
        anchor = re.sub(r"[ _]+", "-", anchor).strip("-")
        if anchor:
            anchors.add(anchor)
    return anchors


def _safe_repository_path(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _schema_errors(schema: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "root"
        errors.append(f"schema {location}: {error.message}")
    return errors


def _identity_errors(paths: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    identifiers = [path.get("id") for path in paths]
    if len(identifiers) != len(set(map(str, identifiers))):
        errors.append("critical path ids must be unique")
    if set(identifiers) != set(EXPECTED_ISSUES):
        errors.append("critical paths must contain the seven canonical ids exactly once")
    issue_numbers = [
        path["issue"].get("number")
        for path in paths
        if isinstance(path.get("issue"), dict)
    ]
    if len(issue_numbers) != len(set(map(str, issue_numbers))):
        errors.append("critical paths must bind unique GitHub issues")
    return errors


def _closure_errors(identifier: object, status: object, closure: object) -> list[str]:
    errors: list[str] = []
    closure_status = closure.get("status") if isinstance(closure, dict) else None
    closure_refs = closure.get("refs") if isinstance(closure, dict) else None
    if identifier in OWNER_ACTION_PATHS and status == "BLOCKED_OWNER_ACTION" and (
        closure_status != "PENDING_OWNER_ACTION" or closure_refs != []
    ):
        errors.append(f"{identifier} blocked state requires pending empty closure evidence")
    if identifier in OWNER_ACTION_PATHS and status != "BLOCKED_OWNER_ACTION" and (
        closure_status != "VERIFIED" or not closure_refs
    ):
        errors.append(f"{identifier} readiness requires explicit verified closure evidence")
    if identifier not in OWNER_ACTION_PATHS and closure != {"status": "NOT_REQUIRED", "refs": []}:
        errors.append(f"{identifier} must not claim owner-action closure evidence")
    return errors


def _issue_and_status_errors(path: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    identifier = path.get("id")
    issue = path.get("issue")
    if isinstance(issue, dict):
        number = issue.get("number")
        expected_number = EXPECTED_ISSUES.get(identifier) if isinstance(identifier, str) else None
        if expected_number is not None and number != expected_number:
            errors.append(f"{identifier} must bind issue #{expected_number}")
        expected_url = f"https://github.com/{REPOSITORY}/issues/{number}"
        if issue.get("url") != expected_url:
            errors.append(f"{identifier} issue URL must be {expected_url}")

    status = path.get("status")
    closure = path.get("closure_evidence")
    errors.extend(_closure_errors(identifier, status, closure))
    if identifier not in OWNER_ACTION_PATHS and status == "BLOCKED_OWNER_ACTION":
        errors.append(f"{identifier} has no declared owner-only prerequisite")
    return errors


def _runbook_errors(path: dict[str, Any], root: Path) -> list[str]:
    identifier = path.get("id")
    runbook = path.get("runbook")
    if not isinstance(runbook, dict) or not isinstance(runbook.get("path"), str):
        return []
    relative = runbook["path"]
    anchor = runbook.get("anchor")
    resolved = _safe_repository_path(root, relative)
    if resolved is None:
        return [f"{identifier} runbook escapes the repository"]
    if not resolved.is_file():
        return [f"{identifier} runbook does not exist: {relative}"]
    if isinstance(anchor, str) and anchor not in _heading_anchors(
        resolved.read_text(encoding="utf-8")
    ):
        return [f"{identifier} runbook anchor does not exist: {relative}#{anchor}"]
    return []


def validate(root: Path = ROOT) -> list[str]:
    """Return every contract violation without querying mutable provider state."""
    try:
        schema = _load_object(root / SCHEMA_PATH)
        contract = _load_object(root / CONTRACT_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    errors = _schema_errors(schema, contract)

    raw_paths = contract.get("critical_paths")
    if not isinstance(raw_paths, list):
        return errors
    paths = [path for path in raw_paths if isinstance(path, dict)]
    errors.extend(_identity_errors(paths))
    for path in paths:
        errors.extend(_issue_and_status_errors(path))
        errors.extend(_runbook_errors(path, root))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"result": "FAIL", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"result": "PASS", "critical_paths": len(EXPECTED_ISSUES)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
