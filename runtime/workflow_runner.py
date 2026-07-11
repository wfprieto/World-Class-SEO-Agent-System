"""Bounded execution of SEO workflow graphs with real handoff consumption."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from runtime.execution_limits import ExecutionLimits
from runtime.executor import AgentExecutor
from runtime.finding_registry import FindingRegistry, build_decisions
from runtime.routing import RouteResult
from runtime.run_budget import BudgetExceeded, RunBudget
from runtime.schema_registry import SchemaRegistry
from runtime.state import Handoff, SessionState
from runtime.tools import ToolRequest
from runtime.workflow_graph import WorkflowNode, build_workflow_graph


class WorkflowRunner:
    def __init__(self, repo_root: Path, executor: AgentExecutor) -> None:
        self.repo_root = repo_root
        self.executor = executor
        self.schemas = SchemaRegistry(repo_root)

    async def run(
        self,
        session: SessionState,
        route: RouteResult,
        tool_requests: list[ToolRequest] | None = None,
        limits: ExecutionLimits | None = None,
    ) -> dict[str, Any]:
        active_limits = limits or ExecutionLimits(max_workflow_depth=5)
        budget = RunBudget(active_limits)
        graph = build_workflow_graph(route, session)
        graph.validate(
            max_nodes=active_limits.max_nodes,
            max_depth=active_limits.max_workflow_depth,
        )
        session.execution_limits = active_limits.to_dict()
        session.workflow_status = "RUNNING"

        tools = await self.executor.tool_dispatcher.dispatch_many(tool_requests or [])
        tool_results = [tool.to_dict() for tool in tools]
        required_tool_failures = [
            tool
            for tool in tools
            if tool.required and tool.evidence_state in {"BLOCKED", "INVALID", "MISSING"}
        ]
        for tool in required_tool_failures:
            session.open_risks.append(
                f"Required tool {tool.tool} did not produce usable evidence: {tool.status}."
            )

        # Open risks are routed to the Scrummaster as a real handoff before specialist work.
        # It remains CREATED until a Scrummaster node actually consumes it.
        if session.open_risks and route.lead_agent != "SEO Scrummaster Agent":
            session.handoffs.append(
                Handoff(
                    handoff_id=f"{session.session_id}-risk-escalation-001",
                    from_agent=route.lead_agent,
                    to_agent="SEO Scrummaster Agent",
                    reason=route.escalation,
                    context_summary="; ".join(session.open_risks)[:1000],
                    evidence_refs=[item.id for item in session.evidence_inventory],
                    requested_action=(
                        "Review the open risks, determine whether the workflow may proceed, "
                        "and record a decision before implementation or publication."
                    ),
                    risk_level="High",
                    acceptance_criteria=[
                        "A schema-valid decision record addresses each open risk.",
                        "No gated implementation proceeds on unresolved evidence.",
                    ],
                    due_trigger="Before implementation or publication.",
                )
            )

        outputs_by_node: dict[str, dict[str, Any]] = {}
        states: dict[str, str] = {}
        errors: dict[str, list[str]] = {}
        semaphore = asyncio.Semaphore(active_limits.max_parallel_agents)

        async def run_node(
            node: WorkflowNode,
            shared_outputs: list[dict[str, Any]],
        ) -> None:
            blocked_dependencies = [
                dependency
                for dependency in node.depends_on
                if states.get(dependency) not in {"COMPLETE", "SYNTHETIC"}
            ]
            if blocked_dependencies:
                states[node.id] = "BLOCKED"
                errors[node.id] = [
                    "Blocked by incomplete dependencies: " + ", ".join(blocked_dependencies)
                ]
                session.add_event(node.id, node.agent, "BLOCKED", errors[node.id][0])
                return

            try:
                budget.reserve_node()
            except BudgetExceeded as exc:
                states[node.id] = "BLOCKED"
                errors[node.id] = [str(exc)]
                session.add_event(node.id, node.agent, "BLOCKED", str(exc))
                return

            dependency_outputs = [outputs_by_node[item] for item in node.depends_on]
            handoffs = self._create_handoffs(session, node, dependency_outputs)
            session.handoffs.extend(handoffs)
            session.add_event(node.id, node.agent, "RUNNING")

            async with semaphore:
                output, result = await self.executor.execute_agent(
                    session,
                    agent_name=node.agent,
                    workflow_path=route.workflow,
                    tool_results=tool_results,
                    prior_outputs=shared_outputs,
                    budget=budget,
                    role=node.role,
                )

            output_id = str(output.get("output_id") or output.get("agent") or node.id)
            # Consume every pending handoff addressed to this agent, including the initial
            # risk escalation and direct dependency handoffs.
            for pending in session.handoffs:
                if pending.status == "CREATED" and pending.to_agent == node.agent:
                    pending.consume(output_id)
            outputs_by_node[node.id] = output
            session.agent_outputs.append(output)
            if result.status == "ok":
                state = "SYNTHETIC" if result.synthetic else "COMPLETE"
            elif result.status == "blocked":
                state = "BLOCKED"
            else:
                state = "FAILED"
            states[node.id] = state
            errors[node.id] = list(result.errors)
            session.add_event(node.id, node.agent, state, "; ".join(result.errors[:3]))

        for level in graph.levels():
            # Every node in a level sees the same completed-state snapshot. This avoids
            # nondeterministic same-level leakage while giving downstream agents all prior
            # validated specialist work, not only the immediately preceding handoff.
            shared_snapshot = list(outputs_by_node.values())
            await asyncio.gather(*(run_node(node, shared_snapshot) for node in level))

        registry = FindingRegistry()
        completed_outputs = [
            output
            for node_id, output in outputs_by_node.items()
            if states.get(node_id) in {"COMPLETE", "SYNTHETIC"}
        ]
        for output in completed_outputs:
            registry.add_output(output)
        conflicts = registry.conflicts(completed_outputs)
        registry.accept_all_without_conflict(conflicts)
        normalized_findings = registry.records()
        decisions = build_decisions(conflicts, normalized_findings)

        scrum_completed = any(
            output.get("agent") == "SEO Scrummaster Agent"
            for output in completed_outputs
        )
        if scrum_completed and not decisions:
            decisions.append(
                {
                    "decision_id": f"{session.session_id}-decision-governance-001",
                    "proposal": "Advance the validated findings to strategy and reporting.",
                    "decision": "Defer" if any(state == "SYNTHETIC" for state in states.values()) else "Approve",
                    "evidence": [
                        str(item.get("id"))
                        for item in normalized_findings
                        if item.get("id")
                    ],
                    "counterarguments": [
                        "Synthetic or incomplete evidence cannot authorize implementation."
                        if any(state == "SYNTHETIC" for state in states.values())
                        else "No unresolved material conflict was detected."
                    ],
                    "risk": "Medium",
                    "owner": "SEO Scrummaster Agent",
                    "conditions": [
                        "Human approval remains required for every gated implementation.",
                        "Replace synthetic evidence before client-facing conclusions."
                        if any(state == "SYNTHETIC" for state in states.values())
                        else "Preserve evidence, owner, acceptance criteria, and rollback controls.",
                    ],
                    "verification": "Validate the complete session state and re-run affected specialists when evidence changes.",
                    "rollback": "Do not implement recommendations that lack verified evidence or approval.",
                }
            )

        for decision in decisions:
            self.schemas.validate("decision-record", decision)
        session.decisions.extend(decisions)

        required_failures = [
            node.id
            for node in graph.nodes
            if node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        optional_failures = [
            node.id
            for node in graph.nodes
            if not node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        has_synthetic = any(state == "SYNTHETIC" for state in states.values())
        unresolved_handoffs = [
            handoff for handoff in session.handoffs if handoff.status != "CONSUMED"
        ]
        if required_failures:
            workflow_status = "FAILED"
        elif optional_failures or required_tool_failures or conflicts or has_synthetic or unresolved_handoffs:
            workflow_status = "PARTIAL"
        else:
            workflow_status = "COMPLETE"
        session.workflow_status = workflow_status
        session.budget_usage = budget.snapshot()

        final_node = next(
            (
                node.id
                for node in reversed(graph.nodes)
                if node.id in outputs_by_node
                and states.get(node.id) in {"COMPLETE", "SYNTHETIC"}
            ),
            None,
        )
        final_output = outputs_by_node.get(final_node) if final_node else None
        consumed = sum(1 for handoff in session.handoffs if handoff.status == "CONSUMED")

        session_payload = session.to_dict()
        self.schemas.validate("session-state", session_payload)
        llm_summary = {
            "provider": getattr(self.executor.llm_client, "provider", "unknown"),
            "model": getattr(self.executor.llm_client, "model", "unknown"),
            "calls": budget.usage.llm_calls,
            "correction_calls": budget.usage.correction_calls,
            "synthetic": has_synthetic,
        }

        return {
            "execution_mode": "multi-agent",
            "route": route.to_dict(),
            "workflow": graph.to_dict(),
            "workflow_status": workflow_status,
            "node_states": states,
            "node_errors": errors,
            "tool_results": tool_results,
            "agent_output": final_output,
            "agent_outputs": completed_outputs,
            "normalized_findings": normalized_findings,
            "conflicts": conflicts,
            "handoffs": [asdict(handoff) for handoff in session.handoffs],
            "handoffs_created": len(session.handoffs),
            "handoffs_consumed": consumed,
            "decisions": decisions,
            "budget": budget.snapshot(),
            "llm": llm_summary,
            "session": session_payload,
        }

    @staticmethod
    def _create_handoffs(
        session: SessionState,
        node: WorkflowNode,
        dependency_outputs: list[dict[str, Any]],
    ) -> list[Handoff]:
        handoffs: list[Handoff] = []
        for index, output in enumerate(dependency_outputs, start=1):
            findings = [
                str(item.get("id"))
                for item in output.get("findings", [])
                if isinstance(item, dict) and item.get("id")
            ]
            handoffs.append(
                Handoff(
                    handoff_id=f"{session.session_id}-{node.id}-handoff-{index:02d}",
                    from_agent=str(output.get("agent", "Unknown Agent")),
                    to_agent=node.agent,
                    reason=f"Dependency output required by workflow node {node.id}.",
                    context_summary=str(output.get("summary", ""))[:1000],
                    evidence_refs=findings,
                    requested_action=(
                        f"Consume this validated output and complete the {node.role} responsibility "
                        "without duplicating unsupported conclusions."
                    ),
                    risk_level=(
                        "High"
                        if any(
                            item.get("severity") in {"Critical", "High"}
                            for item in output.get("findings", [])
                            if isinstance(item, dict)
                        )
                        else "Medium"
                    ),
                    acceptance_criteria=[
                        "The receiving output references or explicitly challenges the supplied evidence.",
                        "Conflicts and missing evidence are not silently discarded.",
                    ],
                    due_trigger=f"Before node {node.id} is complete.",
                )
            )
        return handoffs
