"""Repository-local JSON Schema loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


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
        self._paths: dict[str, Path] = {}
        self._registry: Registry[Any] | None = None

    def _path(self, schema_name: str) -> Path:
        normalized = schema_name.removesuffix(".schema.json").removesuffix(".json")
        if normalized == "session-state":
            return self.repo_root / "orchestration" / "session-state.schema.json"
        return self.schema_root / f"{normalized}.schema.json"

    def load(self, schema_name: str) -> dict[str, Any]:
        key = schema_name.removesuffix(".schema.json").removesuffix(".json")
        if key not in self._schemas:
            path = self._path(key)
            if not path.exists():
                raise FileNotFoundError(f"schema not found: {path}")
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self._schemas[key] = schema
            self._paths[key] = path
        return self._schemas[key]

    def _reference_registry(self) -> Registry[Any]:
        if self._registry is None:
            resources = []
            schema_paths = list(self.schema_root.glob("*.schema.json"))
            schema_paths.append(self.repo_root / "orchestration" / "session-state.schema.json")
            for path in schema_paths:
                if path.exists():
                    contents = json.loads(path.read_text(encoding="utf-8"))
                    resources.append((path.resolve().as_uri(), Resource.from_contents(contents)))
            self._registry = Registry().with_resources(resources)
        return self._registry

    def errors(self, schema_name: str, payload: Any) -> list[str]:
        key = schema_name.removesuffix(".schema.json").removesuffix(".json")
        schema = self.load(key)
        base_uri = self._paths[key].resolve().as_uri()
        registry = self._reference_registry()
        validator = Draft202012Validator(
            schema,
            registry=registry,
            _resolver=registry.resolver(base_uri=base_uri),
        )
        return [
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
        ]

    def validate(self, schema_name: str, payload: Any) -> None:
        errors = self.errors(schema_name, payload)
        if errors:
            raise SchemaValidationError(schema_name, errors)
