"""Executable orchestrator for coordinated SEO agent sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from runtime.execution_limits import ExecutionLimits
from runtime.executor import AgentExecutor
from runtime.llm import LLMClient, build_llm_client
from runtime.memory import MemoryStore
from runtime.routing import RequestRouter, RouteResult
from runtime.state import EvidenceItem, SessionState
from runtime.tools import ToolDispatcher, ToolRequest
from runtime.workflow_runner import WorkflowRunner


class SEOOrchestrator:
    """Runtime facade for routing, state, tools, and multi-agent workflow execution."""

    def __init__(
        self,
        repo_root: Path,
        llm_client: LLMClient | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.router = RequestRouter()
        self.llm_client = llm_client or build_llm_client("echo")
        self.executor = AgentExecutor(
            repo_root=repo_root,
            llm_client=self.llm_client,
            tool_dispatcher=tool_dispatcher,
            memory=memory,
        )
        self.workflow_runner = WorkflowRunner(repo_root, self.executor)

    def start_session(
        self,
        request: str,
        mode: str,
        domain: str = "",
        business_type: str = "unknown",
        markets: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> SessionState:
        session = SessionState.create(
            request=request,
            mode=mode,
            domain=domain,
            business_type=business_type,
            markets=markets,
            goals=goals,
        )
        if not domain:
            session.evidence_inventory.append(
                EvidenceItem(
                    id="missing-domain",
                    source="user_request",
                    type="business_context",
                    status="missing",
                    notes="No target domain or property was supplied.",
                )
            )
            session.open_risks.append("Target domain/property missing; routing is provisional.")
        return session

    def route(self, session: SessionState) -> RouteResult:
        result = self.router.route(session.request)
        session.add_event(
            node_id="routing",
            agent="SEO Scrummaster Agent",
            state="COMPLETE",
            detail=f"Routed request to {result.lead_agent} with {len(result.supporting_agents)} support agents.",
        )
        session.agent_outputs.append(
            {
                "output_id": f"{session.session_id}-routing-output",
                "agent": "SEO Scrummaster Agent",
                "summary": (
                    f"Routed the request to {result.lead_agent} with "
                    f"{len(result.supporting_agents)} supporting agents."
                ),
                "evidence": [
                    {
                        "id": "runtime-route",
                        "source": "runtime_route",
                        "type": "routing_decision",
                        "date_checked": session.created_at[:10],
                        "notes": (
                            f"Workflow: {result.workflow}; routing confidence: {result.confidence}."
                        ),
                    }
                ],
                "confidence": result.confidence if result.confidence in {"High", "Medium", "Low"} else "Low",
                "findings": [
                    {
                        "id": f"{session.session_id}-route-001",
                        "severity": "Low",
                        "finding": f"The request is routed to {result.lead_agent} as deliverable owner.",
                        "affected_scope": result.workflow,
                        "evidence_refs": ["runtime-route"],
                    }
                ],
                "recommended_actions": [
                    {
                        "action": "Execute the routed workflow and record every required specialist output.",
                        "priority": "P2",
                        "owner": result.lead_agent,
                        "success_metric": "Required workflow nodes complete or report a truthful blocked state.",
                    }
                ],
                "impact": "Creates an explicit, reviewable routing decision before specialist execution.",
                "effort": "Low",
                "risks": [result.escalation],
                "owner": "SEO Scrummaster Agent",
                "dependencies": result.required_evidence,
                "acceptance_criteria": [
                    "Lead and support agents exist in the capability registry.",
                    "The selected workflow exists and can build a valid graph.",
                ],
                "verification": [
                    "Validate the routing output against the canonical agent-output schema.",
                    "Confirm the workflow executes the listed specialists rather than retaining metadata only.",
                ],
                "follow_up": "At workflow completion or when routing evidence changes.",
                "material_claims": [],
                "skills_used": ["request-routing"],
                "knowledge_used": [],
                "execution_state": "SYNTHETIC",
            }
        )
        return result

    def load_artifact(self, relative_path: str) -> str:
        path = self.repo_root / relative_path
        return path.read_text(encoding="utf-8")

    def session_snapshot(self, session: SessionState) -> dict[str, Any]:
        return session.to_dict()

    async def execute_async(
        self,
        session: SessionState,
        route: RouteResult | None = None,
        tool_requests: list[ToolRequest] | None = None,
        *,
        execution_mode: str = "multi-agent",
        limits: ExecutionLimits | None = None,
    ) -> dict[str, Any]:
        active_route = route or self.route(session)
        if execution_mode == "single-agent":
            return await self.executor.execute(session, active_route, tool_requests)
        if execution_mode != "multi-agent":
            raise ValueError("execution_mode must be 'multi-agent' or 'single-agent'")
        return await self.workflow_runner.run(
            session,
            active_route,
            tool_requests,
            limits=limits,
        )

    def execute(
        self,
        session: SessionState,
        route: RouteResult | None = None,
        tool_requests: list[ToolRequest] | None = None,
        *,
        execution_mode: str = "multi-agent",
        limits: ExecutionLimits | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.execute_async(
                session,
                route,
                tool_requests,
                execution_mode=execution_mode,
                limits=limits,
            )
        )
