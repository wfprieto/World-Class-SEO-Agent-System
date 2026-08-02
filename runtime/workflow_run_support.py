"""Small run-finalization helpers kept outside the workflow coordinator."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from runtime.executor import AgentExecutor
from runtime.routing import RouteResult
from runtime.run_budget import RunBudget
from runtime.state import Handoff, SessionState
from runtime.tools import REQUIRED_TOOL_FAILURE_STATES
from runtime.workflow_graph import WorkflowGraph, WorkflowNode


def record_required_tool_failures(session: SessionState, tools: list[Any]) -> list[Any]:
    failures = [
        tool for tool in tools
        if tool.required and tool.evidence_state in REQUIRED_TOOL_FAILURE_STATES
    ]
    for tool in failures:
        session.open_risks.append(
            f"Required tool {tool.tool} did not produce usable evidence: {tool.status}."
        )
    return failures


def append_risk_handoff(
    session: SessionState, route: RouteResult, graph: WorkflowGraph
) -> None:
    if not session.open_risks or route.lead_agent == "SEO Scrummaster Agent":
        return
    scrum_node_id = next(
        (node.id for node in graph.nodes if node.agent == "SEO Scrummaster Agent"), ""
    )
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
            target_node_id=scrum_node_id,
        )
    )


def block_node(
    session: SessionState,
    node: WorkflowNode,
    states: dict[str, str],
    errors: dict[str, list[str]],
    detail: str,
) -> None:
    states[node.id] = "BLOCKED"
    errors[node.id] = [detail]
    session.add_event(node.id, node.agent, "BLOCKED", detail)


def node_result_state(status: str, synthetic: bool) -> str:
    if status == "ok":
        return "SYNTHETIC" if synthetic else "COMPLETE"
    return "BLOCKED" if status == "blocked" else "FAILED"


def scrum_completed(outputs: list[dict[str, Any]]) -> bool:
    return any(output.get("agent") == "SEO Scrummaster Agent" for output in outputs)


def default_governance_decision(
    session: SessionState,
    findings: list[dict[str, Any]],
    states: dict[str, str],
) -> dict[str, Any]:
    synthetic = "SYNTHETIC" in states.values()
    return {
        "decision_id": f"{session.session_id}-decision-governance-001",
        "proposal": "Advance the validated findings to strategy and reporting.",
        "decision": "Defer" if synthetic else "Approve",
        "evidence": [str(item.get("id")) for item in findings if item.get("id")],
        "counterarguments": [
            "Synthetic or incomplete evidence cannot authorize implementation."
            if synthetic else "No unresolved material conflict was detected."
        ],
        "risk": "Medium",
        "owner": "SEO Scrummaster Agent",
        "conditions": [
            "Human approval remains required for every gated implementation.",
            "Replace synthetic evidence before client-facing conclusions."
            if synthetic
            else "Preserve evidence, owner, acceptance criteria, and rollback controls.",
        ],
        "verification": (
            "Validate the complete session state and re-run affected specialists when evidence changes."
        ),
        "rollback": "Do not implement recommendations that lack verified evidence or approval.",
    }


def final_output(
    graph: WorkflowGraph,
    outputs: dict[str, dict[str, Any]],
    states: dict[str, str],
) -> dict[str, Any] | None:
    if states.get(graph.deliverable_node_id) not in {"COMPLETE", "SYNTHETIC"}:
        return None
    return outputs.get(graph.deliverable_node_id)


def workflow_status(
    graph: WorkflowGraph,
    states: dict[str, str],
    output: dict[str, Any] | None,
    tool_failures: list[Any],
    conflicts: list[dict[str, Any]],
    synthetic: bool,
    unresolved: list[dict[str, Any]],
) -> str:
    successful = {"COMPLETE", "SYNTHETIC"}
    required_failed = any(
        node.required and states.get(node.id) not in successful for node in graph.nodes
    )
    optional_failed = any(
        not node.required and states.get(node.id) not in successful for node in graph.nodes
    )
    if required_failed or output is None:
        return "FAILED"
    partial = (
        optional_failed or tool_failures or conflicts or synthetic
        or unresolved or graph.capacity_exclusions
    )
    return "PARTIAL" if partial else "COMPLETE"


def run_payload(
    *,
    executor: AgentExecutor,
    session: SessionState,
    route: RouteResult,
    graph: WorkflowGraph,
    budget: RunBudget,
    tool_results: list[dict[str, Any]],
    states: dict[str, str],
    errors: dict[str, list[str]],
    final_output: dict[str, Any] | None,
    completed: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    governance: dict[str, Any],
    decisions: list[dict[str, Any]],
    status: str,
    has_synthetic: bool,
    session_payload: dict[str, Any],
) -> dict[str, Any]:
    consumed = sum(1 for handoff in session.handoffs if handoff.status == "CONSUMED")
    return {
        "execution_mode": "multi-agent", "route": route.to_dict(),
        "workflow": graph.to_dict(), "workflow_status": status,
        "node_states": states, "node_errors": errors, "tool_results": tool_results,
        "agent_output": final_output, "agent_outputs": completed,
        "normalized_findings": findings, "conflicts": conflicts,
        "handoffs": [asdict(handoff) for handoff in session.handoffs],
        "handoffs_created": len(session.handoffs), "handoffs_consumed": consumed,
        "handoff_governance": governance, "decisions": decisions,
        "budget": budget.snapshot(),
        "llm": {
            "provider": getattr(executor.llm_client, "provider", "unknown"),
            "model": getattr(executor.llm_client, "model", "unknown"),
            "calls": budget.usage.llm_calls,
            "correction_calls": budget.usage.correction_calls,
            "synthetic": has_synthetic,
        },
        "session": session_payload,
    }
