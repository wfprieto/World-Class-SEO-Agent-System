"""Knowledge graph/entity consistency adapter."""

from __future__ import annotations

import json
from pathlib import Path

from adapters.base import AdapterResult


class KnowledgeGraphAdapter:
    name = "knowledge_graph"

    def fetch(self, path: str = "", entity: dict | None = None, **_: object) -> AdapterResult:
        data = entity or json.loads(Path(path).read_text(encoding="utf-8"))
        required = ["name", "url", "sameAs"]
        missing = [field for field in required if not data.get(field)]
        warnings = [f"Missing entity field: {field}" for field in missing]
        same_as = data.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        return AdapterResult(source=path or "entity", status="ok" if not warnings else "needs-review", data={"name": data.get("name"), "url": data.get("url"), "sameAs_count": len(same_as)}, warnings=warnings)
