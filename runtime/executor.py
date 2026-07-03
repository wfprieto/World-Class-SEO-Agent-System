"""Async workflow execution for routed SEO agent sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from runtime.llm import LLMClient, LLMMessage
from runtime.memory import InMemoryStore, MemoryStore
from runtime.routing import RouteResult
from runtime.state import SessionState
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
        payload = {
            "route": route.to_dict(),
            "tool_results": [tool.to_dict() for tool in tools],
            "llm": response.to_dict(),
        }
        self.memory.append(session.session_id, {"type": "llm_response", "payload": payload})
        session.agent_outputs.append(
            {
                "agent": route.lead_agent,
                "summary": "Runtime execution completed.",
                "provider": response.provider,
                "model": response.model,
                "content": response.content,
            }
        )
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
