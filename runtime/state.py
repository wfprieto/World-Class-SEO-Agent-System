"""Shared state models for SEO agent workflows."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class BusinessContext:
    domain: str
    business_type: str
    markets: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)


@dataclass
class EvidenceItem:
    id: str
    source: str
    type: str
    status: str
    notes: str = ""


@dataclass
class Handoff:
    handoff_id: str
    from_agent: str
    to_agent: str
    reason: str
    context_summary: str
    evidence_refs: list[str]
    requested_action: str
    risk_level: str
    acceptance_criteria: list[str]
    due_trigger: str


@dataclass
class SessionState:
    session_id: str
    request: str
    mode: str
    business_context: BusinessContext
    evidence_inventory: list[EvidenceItem] = field(default_factory=list)
    agent_outputs: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    open_risks: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        request: str,
        mode: str,
        domain: str,
        business_type: str,
        markets: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> "SessionState":
        return cls(
            session_id=f"seo-session-{uuid4().hex[:12]}",
            request=request,
            mode=mode,
            business_context=BusinessContext(
                domain=domain,
                business_type=business_type,
                markets=markets or [],
                goals=goals or [],
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("created_at", None)
        return data

