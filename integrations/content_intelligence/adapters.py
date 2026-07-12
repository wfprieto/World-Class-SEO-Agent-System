"""ToolDispatcher-compatible wrapper for deterministic content intelligence."""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterResult
from integrations.content_intelligence.service import ContentIntelligenceService


class ContentIntelligenceAdapter:
    """Expose the content intelligence service through one runtime adapter."""

    name = "content_intelligence"

    def __init__(self, service: ContentIntelligenceService | None = None) -> None:
        self.service = service or ContentIntelligenceService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        normalized = operation.strip().lower().replace("_", "-")
        handlers = {
            "quality": self.service.quality,
            "verify": self.service.verify,
            "entities": self.service.entities,
            "brief": self.service.brief,
            "decay": self.service.decay,
            "compare": self.service.compare,
            "humanize": self.service.humanize,
        }
        handler = handlers.get(normalized)
        if handler is None:
            raise ValueError(
                "operation must be quality, verify, entities, brief, decay, "
                "compare, or humanize"
            )
        return handler(**kwargs)
