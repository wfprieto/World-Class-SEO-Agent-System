"""Validate example JSON payloads against repository JSON schemas."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(schema_path: Path, payload_path: Path) -> list[str]:
    schema = load_json(schema_path)
    payload = load_json(payload_path)
    validator = Draft202012Validator(schema)
    return [error.message for error in validator.iter_errors(payload)]


def main() -> int:
    pairs = [
        (ROOT / "schemas/agent-output.schema.json", payload)
        for payload in sorted((ROOT / "examples").glob("*/agent-output.json"))
    ]
    failures: list[str] = []
    for schema_path, payload_path in pairs:
        errors = validate(schema_path, payload_path)
        if errors:
            failures.append(f"{payload_path} failed {schema_path}: {errors}")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("Schema example validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
