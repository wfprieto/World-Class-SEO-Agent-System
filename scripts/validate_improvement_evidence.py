"""Validate improvement-loop governance without executing or approving a cycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from runtime.schema_registry import SchemaRegistry

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def validate_reviewer_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = root / "evaluation" / "reviewer-registry.json"
    registry = _load(path)
    reviewers = registry.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 2:
        return ["reviewer registry must define exactly two reviewers"]

    ids: set[str] = set()
    roles: set[str] = set()
    for reviewer in reviewers:
        reviewer_id = str(reviewer.get("reviewer_id", ""))
        role = str(reviewer.get("role", ""))
        if reviewer_id in ids:
            errors.append(f"duplicate reviewer id: {reviewer_id}")
        ids.add(reviewer_id)
        roles.add(role)
        instructions = root / str(reviewer.get("instructions", ""))
        output_schema = root / str(reviewer.get("output_schema", ""))
        if not instructions.is_file():
            errors.append(f"missing reviewer instructions: {instructions}")
        if not output_schema.is_file():
            errors.append(f"missing reviewer output schema: {output_schema}")
        if reviewer.get("can_modify_code") is not False:
            errors.append(f"{reviewer_id} cannot modify code")
        if reviewer.get("can_modify_scorecard") is not False:
            errors.append(f"{reviewer_id} cannot modify the scorecard")
        if reviewer.get("can_merge") is not False:
            errors.append(f"{reviewer_id} cannot merge")
        if reviewer.get("requires_fresh_context") is not True:
            errors.append(f"{reviewer_id} must require a fresh context")
        if reviewer.get("requires_three_objections") is not True:
            errors.append(f"{reviewer_id} must require at least three objections")

    if roles != {"SENIOR_SCRUMMASTER_3", "VP_ENGINEERING"}:
        errors.append(f"unexpected reviewer roles: {sorted(roles)}")

    independence = registry.get("independence")
    required_true = {
        "distinct_reviewer_ids",
        "distinct_context_ids",
        "other_verdict_hidden_until_submission",
        "builder_cannot_review",
        "one_rejection_blocks_approval",
        "averaging_forbidden",
    }
    if not isinstance(independence, dict):
        errors.append("reviewer registry has no independence policy")
    else:
        for key in sorted(required_true):
            if independence.get(key) is not True:
                errors.append(f"independence policy {key} must be true")
    return errors


def validate_schemas(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    registry = SchemaRegistry(root)
    for schema_name in ("reviewer-verdict", "improvement-cycle"):
        try:
            schema = registry.load(schema_name)
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{schema_name}: {exc}")
    return errors


def validate_cycle_files(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    directory = root / "evaluation" / "cycles"
    if not directory.exists():
        return errors
    registry = SchemaRegistry(root)
    for path in sorted(directory.glob("*.json")):
        payload = _load(path)
        for error in registry.errors("improvement-cycle", payload):
            errors.append(f"{path.relative_to(root)}: {error}")
    return errors


def validate_all(root: Path = ROOT) -> dict[str, Any]:
    errors = [
        *validate_reviewer_registry(root),
        *validate_schemas(root),
        *validate_cycle_files(root),
    ]
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "reviewers": 2,
        "direct_merge_permitted": False,
    }


def main() -> int:
    result = validate_all(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
