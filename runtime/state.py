"""Shared state models for coordinated SEO agent workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    status: str = "CREATED"
    receiving_output_id: str = ""
    consumed_at: str = ""

    def consume(self, output_id: str) -> None:
        self.status = "CONSUMED"
        self.receiving_output_id = output_id
        self.consumed_at = datetime.now(timezone.utc).isoformat()

    def block(self) -> None:
        self.status = "BLOCKED"


@dataclass
class WorkflowEvent:
    event_id: str
    node_id: str
    agent: str
    state: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detail: str = ""


@dataclass
class SessionState:
    session_id: str
    request: str
    mode: str
    business_context: BusinessContext
    business_profile_resolution: dict[str, Any] = field(default_factory=dict)
    evidence_inventory: list[EvidenceItem] = field(default_factory=list)
    agent_outputs: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    open_risks: list[str] = field(default_factory=list)
    workflow_status: str = "PLANNED"
    workflow_events: list[WorkflowEvent] = field(default_factory=list)
    execution_limits: dict[str, Any] = field(default_factory=dict)
    budget_usage: dict[str, Any] = field(default_factory=dict)
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

    def add_event(self, node_id: str, agent: str, state: str, detail: str = "") -> None:
        self.workflow_events.append(
            WorkflowEvent(
                event_id=f"{self.session_id}-event-{len(self.workflow_events) + 1:04d}",
                node_id=node_id,
                agent=agent,
                state=state,
                detail=detail,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("created_at", None)
        return data
