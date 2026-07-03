"""Minimal executable orchestrator for SEO agent sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.executor import AgentExecutor
from runtime.llm import LLMClient, build_llm_client
from runtime.memory import MemoryStore
from runtime.routing import RequestRouter, RouteResult
from runtime.state import EvidenceItem, SessionState
from runtime.tools import ToolDispatcher, ToolRequest


class SEOOrchestrator:
    """Runtime facade for routing, state creation, and artifact loading."""

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
        session.agent_outputs.append(
            {
                "agent": "SEO Scrummaster Agent",
                "summary": f"Routed request to {result.lead_agent}.",
                "route": result.to_dict(),
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
    ) -> dict[str, Any]:
        active_route = route or self.route(session)
        return await self.executor.execute(session, active_route, tool_requests)

    def execute(
        self,
        session: SessionState,
        route: RouteResult | None = None,
        tool_requests: list[ToolRequest] | None = None,
    ) -> dict[str, Any]:
        active_route = route or self.route(session)
        return self.executor.execute_sync(session, active_route, tool_requests)
