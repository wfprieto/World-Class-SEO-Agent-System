"""Bounded execution of SEO workflow graphs with evidence-backed handoff consumption."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from runtime.execution_limits import ExecutionLimits
from runtime.executor import AgentExecutor
from runtime.finding_registry import FindingRegistry, build_decisions
from runtime.handoff_governance import (
    reconcile_required_handoffs,
    resolve_handoff_acknowledgements,
)
from runtime.routing import RouteResult
from runtime.run_budget import BudgetExceeded, RunBudget
from runtime.schema_registry import SchemaRegistry
from runtime.state import Handoff, SessionState
from runtime.tools import ToolRequest
from runtime.workflow_graph import WorkflowGraph, WorkflowNode, build_workflow_graph
from runtime.workflow_run_support import (
    append_risk_handoff,
    block_node,
    default_governance_decision,
    final_output,
    node_result_state,
    record_required_tool_failures,
    run_payload,
    scrum_completed,
    workflow_status,
)


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
        graph.validate(max_nodes=active_limits.max_nodes, max_depth=active_limits.max_workflow_depth)
        session.execution_limits = active_limits.to_dict()
        session.workflow_status = "RUNNING"
        tools = await self.executor.tool_dispatcher.dispatch_many(tool_requests or [])
        tool_results = [tool.to_dict() for tool in tools]
        required_tool_failures = record_required_tool_failures(session, tools)
        append_risk_handoff(session, route, graph)
        outputs, states, errors = await self._execute_graph(
            session, route, graph, budget, tool_results, active_limits
        )
        completed, findings, conflicts, decisions = self._reconcile_outputs(
            session, outputs, states
        )
        return self._finalize_run(
            session=session,
            route=route,
            graph=graph,
            budget=budget,
            tool_results=tool_results,
            required_tool_failures=required_tool_failures,
            outputs=outputs,
            states=states,
            errors=errors,
            completed=completed,
            findings=findings,
            conflicts=conflicts,
            decisions=decisions,
        )

    async def _execute_graph(
        self,
        session: SessionState,
        route: RouteResult,
        graph: WorkflowGraph,
        budget: RunBudget,
        tool_results: list[dict[str, Any]],
        limits: ExecutionLimits,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, list[str]]]:
        outputs: dict[str, dict[str, Any]] = {}
        states: dict[str, str] = {}
        errors: dict[str, list[str]] = {}
        semaphore = asyncio.Semaphore(limits.max_parallel_agents)
        for level in graph.levels():
            shared = list(outputs.values())
            await asyncio.gather(
                *(
                    self._execute_node(
                        session, route, node, budget, tool_results, shared,
                        semaphore, outputs, states, errors
                    )
                    for node in level
                )
            )
        return outputs, states, errors

    async def _execute_node(
        self,
        session: SessionState,
        route: RouteResult,
        node: WorkflowNode,
        budget: RunBudget,
        tool_results: list[dict[str, Any]],
        shared_outputs: list[dict[str, Any]],
        semaphore: asyncio.Semaphore,
        outputs: dict[str, dict[str, Any]],
        states: dict[str, str],
        errors: dict[str, list[str]],
    ) -> None:
        blocked = [
            dependency
            for dependency in node.depends_on
            if states.get(dependency) not in {"COMPLETE", "SYNTHETIC"}
        ]
        if blocked:
            block_node(session, node, states, errors, "Blocked by incomplete dependencies: " + ", ".join(blocked))
            return
        try:
            budget.reserve_node()
        except BudgetExceeded as exc:
            block_node(session, node, states, errors, str(exc))
            return
        dependencies = [outputs[item] for item in node.depends_on]
        session.handoffs.extend(self._create_handoffs(session, node, dependencies))
        session.add_event(node.id, node.agent, "RUNNING")
        async with semaphore:
            output, result = await self.executor.execute_agent(
                session,
                agent_name=node.agent,
                workflow_path=route.workflow,
                tool_results=tool_results,
                prior_outputs=shared_outputs,
                required_handoffs=_addressed_handoff_payloads(session, node),
                budget=budget,
                role=node.role,
            )
        output_id = str(output.get("output_id") or output.get("agent") or node.id)
        _resolve_node_handoffs(session, node, output, output_id)
        outputs[node.id] = output
        session.agent_outputs.append(output)
        state = node_result_state(result.status, result.synthetic, output)
        states[node.id] = state
        errors[node.id] = list(result.errors)
        session.add_event(node.id, node.agent, state, "; ".join(result.errors[:3]))

    def _reconcile_outputs(
        self,
        session: SessionState,
        outputs: dict[str, dict[str, Any]],
        states: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        completed = [
            output for node_id, output in outputs.items()
            if states.get(node_id) in {"COMPLETE", "SYNTHETIC"}
        ]
        registry = FindingRegistry()
        for output in completed:
            registry.add_output(output)
        conflicts = registry.conflicts(completed)
        registry.accept_all_without_conflict(conflicts)
        findings = registry.records()
        decisions = build_decisions(conflicts, findings)
        if scrum_completed(completed) and not decisions:
            decisions.append(default_governance_decision(session, findings, states))
        for decision in decisions:
            self.schemas.validate("decision-record", decision)
        session.decisions.extend(decisions)
        return completed, findings, conflicts, decisions

    def _finalize_run(
        self,
        *,
        session: SessionState,
        route: RouteResult,
        graph: WorkflowGraph,
        budget: RunBudget,
        tool_results: list[dict[str, Any]],
        required_tool_failures: list[Any],
        outputs: dict[str, dict[str, Any]],
        states: dict[str, str],
        errors: dict[str, list[str]],
        completed: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        governance = reconcile_required_handoffs(
            session_id=session.session_id,
            graph=graph,
            node_states=states,
            outputs_by_node=outputs,
            handoffs=session.handoffs,
        )
        final_result = final_output(graph, outputs, states)
        has_synthetic = "SYNTHETIC" in states.values()
        status = workflow_status(
            graph, states, final_result, required_tool_failures,
            conflicts, has_synthetic, governance["unresolved"]
        )
        session.workflow_status = status
        session.budget_usage = budget.snapshot()
        session_payload = session.to_dict()
        self.schemas.validate("session-state", session_payload)
        return run_payload(
            executor=self.executor,
            session=session,
            route=route,
            graph=graph,
            budget=budget,
            tool_results=tool_results,
            states=states,
            errors=errors,
            final_output=final_result,
            completed=completed,
            findings=findings,
            conflicts=conflicts,
            governance=governance,
            decisions=decisions,
            status=status,
            has_synthetic=has_synthetic,
            session_payload=session_payload,
        )

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
                    source_node_id=node.depends_on[index - 1],
                    target_node_id=node.id,
                )
            )
        return handoffs


def _addressed_handoff_payloads(
    session: SessionState,
    node: WorkflowNode,
) -> list[dict[str, Any]]:
    return [
        asdict(handoff)
        for handoff in session.handoffs
        if handoff.status == "CREATED"
        and handoff.to_agent == node.agent
        and handoff.target_node_id in {"", node.id}
    ]


def _resolve_node_handoffs(
    session: SessionState,
    node: WorkflowNode,
    output: dict[str, Any],
    output_id: str,
) -> None:
    raw_acknowledgements = output.get("handoff_acknowledgements", [])
    acknowledgements = [item for item in raw_acknowledgements if isinstance(item, dict)]
    for pending in session.handoffs:
        if (
            pending.status != "CREATED"
            or pending.to_agent != node.agent
            or pending.target_node_id not in {"", node.id}
        ):
            continue
        matches = [
            item
            for item in acknowledgements
            if item.get("handoff_id") == pending.handoff_id
        ]
        resolve_handoff_acknowledgements(
            pending,
            matches,
            output_id=output_id,
            node_id=node.id,
            output_agent=str(output.get("agent", "")),
        )
