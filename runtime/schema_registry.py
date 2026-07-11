"""Repository-local JSON Schema loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SchemaValidationError(ValueError):
    """Raised when a runtime artifact does not satisfy its canonical schema."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        super().__init__(f"{schema_name} validation failed: {'; '.join(errors)}")


class SchemaRegistry:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.schema_root = repo_root / "schemas"
        self._schemas: dict[str, dict[str, Any]] = {}

    def load(self, schema_name: str) -> dict[str, Any]:
        key = schema_name if schema_name.endswith(".json") else f"{schema_name}.schema.json"
        if key not in self._schemas:
            path = self.schema_root / key
            if not path.exists():
                raise FileNotFoundError(f"schema not found: {path}")
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self._schemas[key] = schema
        return self._schemas[key]

    def errors(self, schema_name: str, payload: Any) -> list[str]:
        schema = self.load(schema_name)
        validator = Draft202012Validator(schema)
        return [
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
        ]

    def validate(self, schema_name: str, payload: Any) -> None:
        errors = self.errors(schema_name, payload)
        if errors:
            raise SchemaValidationError(schema_name, errors)
