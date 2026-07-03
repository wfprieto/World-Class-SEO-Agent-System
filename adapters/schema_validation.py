"""JSON-LD structured data validation helpers."""

from __future__ import annotations

import json
from typing import Any

from adapters.base import AdapterResult


class SchemaValidationAdapter:
    name = "schema_validation"

    def fetch(self, jsonld: str | dict[str, Any], **_: object) -> AdapterResult:
        warnings: list[str] = []
        if isinstance(jsonld, str):
            try:
                data = json.loads(jsonld)
            except json.JSONDecodeError as exc:
                return AdapterResult(source="jsonld", status="invalid", data={"error": str(exc)}, warnings=["Invalid JSON-LD"])
        else:
            data = jsonld

        if "@context" not in data:
            warnings.append("Missing @context.")
        if "@type" not in data:
            warnings.append("Missing @type.")
        return AdapterResult(
            source="jsonld",
            status="ok" if not warnings else "needs-review",
            data={"type": data.get("@type"), "context": data.get("@context")},
            warnings=warnings,
        )

