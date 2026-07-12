from __future__ import annotations

from typing import Any

from adapters.base import AdapterResult
from integrations.product_proof.intelligence import (
    AICitationOpportunityAnalyzer,
    AITimeoutAnalyzer,
    PerformanceNarrativeAnalyzer,
    ReviewComplianceAnalyzer,
)
from integrations.product_proof.service import ProductProofTechnicalAudit


class ProductProofTechnicalAuditAdapter:
    name = "product_proof_technical_audit"

    def __init__(self) -> None:
        self.service = ProductProofTechnicalAudit()

    def fetch(self, operation: str = "technical", **kwargs: Any) -> AdapterResult:
        if operation != "technical":
            raise ValueError(f"unsupported product-proof audit operation: {operation}")
        return self.service.run(**kwargs)


class ProductProofIntelligenceAdapter:
    name = "product_proof_intelligence"

    def __init__(self) -> None:
        self.timeouts = AITimeoutAnalyzer()
        self.citations = AICitationOpportunityAnalyzer()
        self.reviews = ReviewComplianceAnalyzer()
        self.narrative = PerformanceNarrativeAnalyzer()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        handlers = {
            "ai_timeouts": self.timeouts.analyze,
            "ai_citations": self.citations.analyze,
            "review_compliance": self.reviews.analyze,
            "performance_narrative": self.narrative.analyze,
        }
        if operation not in handlers:
            raise ValueError(f"unsupported product-proof intelligence operation: {operation}")
        return handlers[operation](**kwargs)
