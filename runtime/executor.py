"""Async workflow execution for routed SEO agent sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from runtime.llm import LLMClient, LLMMessage
from runtime.memory import InMemoryStore, MemoryStore
from runtime.routing import RouteResult
from runtime.state import Handoff, SessionState
from runtime.tools import ToolDispatcher, ToolRequest


AGENT_FILE_NAMES = {
    "SEO Technical Agent": "seo-technical-agent.md",
    "SEO Copywriter/Content Agent": "seo-copywriter-content-agent.md",
    "SEO Information Architecture Agent": "seo-information-architecture-agent.md",
    "SEO Accessibility Agent": "seo-accessibility-agent.md",
    "SEO CRO Agent": "seo-cro-agent.md",
    "Local SEO Agent": "local-seo-agent.md",
    "Senior SEO Strategist Agent": "senior-seo-strategist-agent.md",
    "Senior SEO Engineer Agent": "senior-seo-engineer-agent.md",
    "SEO Scrummaster Agent": "seo-scrummaster-agent.md",
    "SEO Full Audit/Analyst Agent": "seo-full-audit-analyst-agent.md",
    "SEO Output Report Agent": "seo-output-report-agent.md",
    "SEO Diagnostic Infrastructure Agent": "seo-diagnostic-infrastructure-agent.md",
    "GEO / AIO Optimization Agent": "geo-aio-optimization-agent.md",
    "Visual & Video Search Agent": "visual-video-search-agent.md",
    "Voice Search & Conversational Agent": "voice-search-conversational-agent.md",
    "SEO Compliance & Legal Agent": "seo-compliance-legal-agent.md",
    "Negative SEO & Security Agent": "negative-seo-security-agent.md",
    "International & Multilingual SEO Agent": "international-multilingual-seo-agent.md",
    "Digital PR & Programmatic Link Outreach Agent": "digital-pr-programmatic-link-outreach-agent.md",
    "Predictive SEO Trend Agent": "predictive-seo-trend-agent.md",
    "Competitive Intelligence Agent": "competitive-intelligence-agent.md",
    "SEO Research and Development Agent": "seo-research-and-development-agent.md",
    "SEO Knowledge Graph Sync Agent": "seo-knowledge-graph-sync-agent.md",
    "AI Principal SEO Scientist": "ai-principal-seo-scientist.md",
    "SEO E-commerce Agent": "seo-ecommerce-agent.md",
}


class AgentExecutor:
    def __init__(
        self,
        repo_root: Path,
        llm_client: LLMClient,
        tool_dispatcher: ToolDispatcher | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.llm_client = llm_client
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.memory = memory or InMemoryStore()

    async def execute(
        self,
        session: SessionState,
        route: RouteResult,
        tool_requests: list[ToolRequest] | None = None,
    ) -> dict[str, Any]:
        tools = await self.tool_dispatcher.dispatch_many(tool_requests or [])
        messages = self._messages(session, route, [tool.to_dict() for tool in tools])
        self.memory.append(session.session_id, {"type": "prompt", "messages": [message.__dict__ for message in messages]})
        response = await self.llm_client.complete(messages)
        agent_output = self._agent_output(session, route, [tool.to_dict() for tool in tools], response.content)
        handoffs = self._handoffs(session, route, response.content, agent_output)
        payload = {
            "route": route.to_dict(),
            "tool_results": [tool.to_dict() for tool in tools],
            "agent_output": agent_output,
            "handoffs": [handoff.__dict__ for handoff in handoffs],
            "llm": response.to_dict(),
        }
        self.memory.append(session.session_id, {"type": "llm_response", "payload": payload})
        session.agent_outputs.append(agent_output)
        session.handoffs.extend(handoffs)
        return payload

    async def stream(
        self,
        session: SessionState,
        route: RouteResult,
        tool_requests: list[ToolRequest] | None = None,
    ) -> AsyncIterator[str]:
        tools = await self.tool_dispatcher.dispatch_many(tool_requests or [])
        messages = self._messages(session, route, [tool.to_dict() for tool in tools])
        self.memory.append(session.session_id, {"type": "stream_prompt", "messages": [message.__dict__ for message in messages]})
        async for chunk in self.llm_client.stream(messages):
            yield chunk

    def execute_sync(
        self,
        session: SessionState,
        route: RouteResult,
        tool_requests: list[ToolRequest] | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(self.execute(session, route, tool_requests))

    def _messages(self, session: SessionState, route: RouteResult, tool_results: list[dict[str, Any]]) -> list[LLMMessage]:
        system_spec = self._read("SYSTEM_SPEC.md")
        agent_file = AGENT_FILE_NAMES.get(route.lead_agent, "seo-scrummaster-agent.md")
        agent_spec = self._read(f"agents/{agent_file}")
        workflow = self._read(route.workflow)
        user_context = {
            "request": session.request,
            "mode": session.mode,
            "business_context": session.business_context.__dict__,
            "route": route.to_dict(),
            "tool_results": tool_results,
            "memory": self.memory.load(session.session_id)[-5:],
        }
        return [
            LLMMessage(role="system", content=system_spec),
            LLMMessage(role="system", content=agent_spec),
            LLMMessage(role="system", content=workflow),
            LLMMessage(
                role="user",
                content=(
                    "Execute the routed SEO workflow using the supplied context. "
                    "Return evidence-backed output that follows the standard agent output contract.\n\n"
                    f"{user_context}"
                ),
            ),
        ]

    def _read(self, relative_path: str) -> str:
        path = self.repo_root / relative_path
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _agent_output(
        self,
        session: SessionState,
        route: RouteResult,
        tool_results: list[dict[str, Any]],
        content: str,
    ) -> dict[str, Any]:
        evidence = [
            {
                "source": result.get("tool", "runtime"),
                "type": "adapter_result",
                "date_checked": session.created_at[:10],
                "notes": f"Adapter status: {result.get('status', 'unknown')}.",
            }
            for result in tool_results
        ] or [
            {
                "source": "runtime_request",
                "type": "business_context",
                "date_checked": session.created_at[:10],
                "notes": "No adapter evidence supplied; output is based on request context and loaded system files.",
            }
        ]
        finding_severity = "Medium" if session.open_risks else "Low"
        return {
            "agent": route.lead_agent,
            "summary": "Runtime execution completed with routed workflow context.",
            "evidence": evidence,
            "confidence": route.confidence if route.confidence in {"High", "Medium", "Low"} else "Medium",
            "findings": [
                {
                    "id": f"{session.session_id}-runtime-001",
                    "severity": finding_severity,
                    "finding": content[:500] if content else "Runtime produced no narrative content.",
                    "affected_scope": session.business_context.domain or "Unspecified domain/property",
                    "evidence_refs": [item["source"] for item in evidence],
                }
            ],
            "recommended_actions": [
                {
                    "action": "Review the routed output, resolve missing evidence, and run the relevant specialist workflow.",
                    "priority": "P1" if session.open_risks else "P2",
                    "owner": route.lead_agent,
                    "success_metric": "Output has verified evidence, owner, acceptance criteria and follow-up trigger.",
                }
            ],
            "impact": "Improves routing clarity and keeps runtime output aligned to the standard SEO agent contract.",
            "effort": "Low",
            "risks": session.open_risks or ["No material runtime risks were detected."],
            "owner": route.lead_agent,
            "dependencies": route.required_evidence,
            "acceptance_criteria": [
                "Agent output conforms to schemas/agent-output.schema.json.",
                "Missing evidence is either supplied or explicitly documented.",
            ],
            "verification": [
                "Validate payload against agent-output schema.",
                "Run repository validation and semantic tests.",
            ],
            "follow_up": "Recheck after missing evidence is supplied or before implementation begins.",
        }

    def _handoffs(
        self,
        session: SessionState,
        route: RouteResult,
        content: str,
        agent_output: dict[str, Any],
    ) -> list[Handoff]:
        should_escalate = bool(session.open_risks) or "escalate" in content.lower() or "handoff" in content.lower()
        if not should_escalate or route.lead_agent == "SEO Scrummaster Agent":
            return []
        return [
            Handoff(
                handoff_id=f"{session.session_id}-handoff-001",
                from_agent=route.lead_agent,
                to_agent="SEO Scrummaster Agent",
                reason=route.escalation,
                context_summary=agent_output["summary"],
                evidence_refs=[finding["id"] for finding in agent_output["findings"]],
                requested_action="Review escalation trigger, confirm owner, and decide whether the workflow can proceed.",
                risk_level="Medium" if session.open_risks else "Low",
                acceptance_criteria=[
                    "Escalation decision is recorded.",
                    "Missing evidence or risk owner is assigned.",
                ],
                due_trigger="Before implementation or publication.",
            )
        ]
