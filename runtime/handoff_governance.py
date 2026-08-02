"""Deterministic, bounded reconciliation for required workflow handoffs.

This module validates explicit dependency edges and exact runtime-declared
open-risk controls in a materialized ``WorkflowGraph``. It intentionally does
not infer semantic handoffs from natural-language agent output.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from runtime.handoff_control_governance import audit_declared_controls
from runtime.handoff_receipts import seal_terminal_handoff, terminal_receipt_is_valid
from runtime.state import Handoff
from runtime.workflow_graph import WorkflowGraph, WorkflowNode


def resolve_handoff_acknowledgements(
    handoff: Handoff,
    acknowledgements: list[dict[str, Any]],
    *,
    output_id: str,
    node_id: str,
    output_agent: str,
) -> None:
    """Apply one exact acknowledgement or leave the handoff pending.

    Exact list equality is set-like but multiplicity-sensitive. A partial or
    forged evidence list, copied action, omitted criterion, duplicate record,
    unknown disposition, or wrong node cannot mark the handoff consumed.
    """
    matches = [
        item for item in acknowledgements if item.get("handoff_id") == handoff.handoff_id
    ]
    if not matches:
        return
    if len(matches) != 1:
        _invalid_ack(handoff, "Duplicate acknowledgements were returned for this handoff.")
        return
    acknowledgement = matches[0]
    disposition = acknowledgement.get("disposition")
    exact = _ack_context_is_exact(
        handoff, acknowledgement, output_id, node_id, output_agent
    )
    note = str(acknowledgement.get("resolution_note", ""))
    if disposition == "UNRESOLVED" and exact and note.strip():
        handoff.receiving_output_id = output_id
        handoff.receiving_node_id = node_id
        handoff.block(note)
        seal_terminal_handoff(handoff)
    elif (
        disposition in {"ACCEPTED", "CHALLENGED"}
        and exact
        and note.strip()
        and (bool(handoff.evidence_refs) or disposition == "CHALLENGED")
    ):
        handoff.consume(output_id, node_id, str(disposition))
        seal_terminal_handoff(handoff)
    else:
        _invalid_ack(
            handoff,
            "Invalid acknowledgement: exact recipient, output, action, evidence, criteria, disposition, and nonblank resolution note are required.",
        )


def _ack_context_is_exact(
    handoff: Handoff,
    acknowledgement: dict[str, Any],
    output_id: str,
    node_id: str,
    output_agent: str,
) -> bool:
    return (
        bool(output_id.strip())
        and node_id == handoff.target_node_id
        and output_agent == handoff.to_agent
        and acknowledgement.get("requested_action_addressed") == handoff.requested_action
        and sorted(acknowledgement.get("evidence_refs_addressed", []))
        == sorted(handoff.evidence_refs)
        and sorted(acknowledgement.get("acceptance_criteria_addressed", []))
        == sorted(handoff.acceptance_criteria)
    )


def _invalid_ack(handoff: Handoff, reason: str) -> None:
    handoff.block(reason)
    seal_terminal_handoff(handoff)


def expected_handoff_id(session_id: str, node_id: str, index: int) -> str:
    """Return the stable identifier used for one dependency edge."""
    return f"{session_id}-{node_id}-handoff-{index:02d}"


def reconcile_required_handoffs(
    *,
    session_id: str,
    graph: WorkflowGraph,
    node_states: dict[str, str],
    outputs_by_node: dict[str, dict[str, Any]],
    handoffs: Iterable[Handoff],
) -> dict[str, Any]:
    """Reconcile graph-required handoffs and return an explicit audit report.

    An edge is required when both its dependency and receiver executed to a
    completed or synthetic state. Missing, duplicate, foreign-session,
    misaddressed, incorrectly consumed, and silently dropped records fail the
    audit. Pending records are converted to explicit ``BLOCKED`` records so a
    caller can never mistake absence of consumption for successful delivery.
    """
    records = list(handoffs)
    by_id, issues = _index_handoffs(records, session_id)
    expected_ids, edge_issues = _audit_graph_edges(
        session_id, graph, node_states, outputs_by_node, by_id
    )
    issues.extend(edge_issues)
    declared_ids, control_issues = audit_declared_controls(
        graph.declared_control_handoffs, by_id, outputs_by_node
    )
    issues.extend(control_issues)
    issues.extend(
        _unexpected_handoffs(records, session_id, expected_ids | declared_ids)
    )
    issues.extend(_finalize_pending(records))

    unresolved = [
        {
            "handoff_id": handoff.handoff_id,
            "status": handoff.status,
            "reason": handoff.unresolved_reason,
        }
        for handoff in records
        if handoff.status != "CONSUMED"
    ]
    consumed_dependency_handoffs = sum(
        1
        for handoff_id in expected_ids
        if len(by_id.get(handoff_id, [])) == 1
        and by_id[handoff_id][0].status == "CONSUMED"
        and terminal_receipt_is_valid(by_id[handoff_id][0])
    )
    return {
        "scope": "materialized-dependency-edges-and-exact-declared-risk-controls",
        "status": "PASS" if not issues and not unresolved else "FAIL",
        "expected_dependency_handoffs": len(expected_ids),
        "declared_risk_control_handoffs": len(declared_ids),
        "consumed_dependency_handoffs": consumed_dependency_handoffs,
        # Compatibility aliases retained for existing report consumers.
        "expected_required": len(expected_ids),
        "consumed_required": consumed_dependency_handoffs,
        "issues": issues,
        "unresolved": unresolved,
        "handoffs": [asdict(handoff) for handoff in records],
    }


def _issue(code: str, handoff_id: str, detail: str) -> dict[str, str]:
    return {"code": code, "handoff_id": handoff_id, "detail": detail}


def _index_handoffs(
    records: list[Handoff],
    session_id: str,
) -> tuple[dict[str, list[Handoff]], list[dict[str, str]]]:
    by_id: dict[str, list[Handoff]] = {}
    for handoff in records:
        by_id.setdefault(handoff.handoff_id, []).append(handoff)
    issues: list[dict[str, str]] = []
    for handoff_id, matches in sorted(by_id.items()):
        if len(matches) > 1:
            issues.append(_issue("DUPLICATE_HANDOFF", handoff_id, "handoff_id is not unique"))
        if not handoff_id.startswith(f"{session_id}-"):
            issues.append(
                _issue(
                    "STALE_HANDOFF",
                    handoff_id,
                    "handoff belongs to a different or unidentifiable session",
                )
            )
    return by_id, issues


def _audit_graph_edges(
    session_id: str,
    graph: WorkflowGraph,
    node_states: dict[str, str],
    outputs_by_node: dict[str, dict[str, Any]],
    by_id: dict[str, list[Handoff]],
) -> tuple[set[str], list[dict[str, str]]]:
    expected_ids: set[str] = set()
    issues: list[dict[str, str]] = []
    nodes = {node.id: node for node in graph.nodes}
    for node, dependency_id, index in _required_edges(graph, node_states):
        handoff_id = expected_handoff_id(session_id, node.id, index)
        expected_ids.add(handoff_id)
        sender = outputs_by_node.get(dependency_id, {}).get(
            "agent", nodes[dependency_id].agent
        )
        issues.extend(
            _audit_required_edge(
                handoff_id=handoff_id,
                matches=by_id.get(handoff_id, []),
                dependency_id=dependency_id,
                node_id=node.id,
                node_agent=node.agent,
                expected_sender=str(sender),
                receiver_output=outputs_by_node.get(node.id, {}),
            )
        )
    return expected_ids, issues


def _finalize_pending(records: list[Handoff]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for handoff in records:
        if handoff.status != "CREATED":
            continue
        handoff.block("No addressed output consumed this handoff before workflow completion.")
        seal_terminal_handoff(handoff)
        issues.append(
            _issue(
                "SILENTLY_DROPPED_HANDOFF",
                handoff.handoff_id,
                handoff.unresolved_reason,
            )
        )
    return issues


def _unexpected_handoffs(
    records: list[Handoff], session_id: str, allowed_ids: set[str]
) -> list[dict[str, str]]:
    return [
        _issue(
            "UNEXPECTED_HANDOFF",
            handoff.handoff_id,
            "current-session handoff is not an exact required materialized graph edge",
        )
        for handoff in records
        if handoff.handoff_id.startswith(f"{session_id}-")
        and handoff.handoff_id not in allowed_ids
    ]


def _required_edges(
    graph: WorkflowGraph,
    node_states: dict[str, str],
) -> Iterable[tuple[WorkflowNode, str, int]]:
    completed = {"COMPLETE", "SYNTHETIC"}
    for node in graph.nodes:
        if node_states.get(node.id) not in completed:
            continue
        for index, dependency_id in enumerate(node.depends_on, start=1):
            if node_states.get(dependency_id) in completed:
                yield node, dependency_id, index


def _audit_required_edge(
    *,
    handoff_id: str,
    matches: list[Handoff],
    dependency_id: str,
    node_id: str,
    node_agent: str,
    expected_sender: str,
    receiver_output: dict[str, Any],
) -> list[dict[str, str]]:
    if not matches:
        return [
            _issue(
                "MISSING_HANDOFF",
                handoff_id,
                f"required dependency {dependency_id} was not handed to {node_id}",
            )
        ]
    handoff = matches[0]
    result: list[dict[str, str]] = []
    if (
        handoff.to_agent != node_agent
        or handoff.from_agent != expected_sender
        or handoff.source_node_id != dependency_id
        or handoff.target_node_id != node_id
    ):
        result.append(
            _issue(
                "WRONG_RECIPIENT",
                handoff_id,
                f"expected {dependency_id}/{expected_sender} -> {node_id}/{node_agent}",
            )
        )
    if _terminal_has_wrong_consumer(handoff, node_id, node_agent, receiver_output):
        result.append(
            _issue(
                "WRONG_CONSUMER",
                handoff_id,
                "consumption is not bound to the exact addressed workflow node output",
            )
        )
    elif handoff.status == "CREATED":
        handoff.block("No exact acknowledgement resolved this required handoff.")
        seal_terminal_handoff(handoff)
        result.append(
            _issue("SILENTLY_DROPPED_HANDOFF", handoff_id, handoff.unresolved_reason)
        )
    elif not terminal_receipt_is_valid(handoff):
        result.append(
            _issue(
                "INVALID_TERMINAL_RECEIPT",
                handoff_id,
                "terminal handoff fields do not match an exact resolver receipt",
            )
        )
    return result


def _terminal_has_wrong_consumer(
    handoff: Handoff,
    node_id: str,
    node_agent: str,
    receiver_output: dict[str, Any],
) -> bool:
    context_bound = handoff.status == "CONSUMED" or (
        handoff.status == "BLOCKED" and bool(handoff.receiving_output_id)
    )
    return context_bound and (
        handoff.receiving_output_id != str(receiver_output.get("output_id", ""))
        or handoff.receiving_node_id != node_id
        or receiver_output.get("agent") != node_agent
    )
