from __future__ import annotations

from copy import deepcopy

import pytest

from runtime.handoff_governance import (
    reconcile_required_handoffs,
    resolve_handoff_acknowledgements,
)
from runtime.routing import RouteResult
from runtime.state import Handoff, SessionState
from runtime.workflow_graph import WorkflowGraph, WorkflowNode, build_workflow_graph

SESSION = "seo-session-fixture"
HANDOFF_ID = f"{SESSION}-receiver-handoff-01"


def _graph() -> WorkflowGraph:
    return WorkflowGraph(
        id="handoff-fixture",
        nodes=[
            WorkflowNode(id="source", agent="Source Agent"),
            WorkflowNode(
                id="receiver",
                agent="Receiver Agent",
                depends_on=("source",),
            ),
        ],
        deliverable_node_id="receiver",
    )


def _handoff() -> Handoff:
    handoff = Handoff(
        handoff_id=HANDOFF_ID,
        from_agent="Source Agent",
        to_agent="Receiver Agent",
        reason="Required dependency.",
        context_summary="Bounded fixture.",
        evidence_refs=["evidence-1"],
        requested_action="Consume the evidence.",
        risk_level="Medium",
        acceptance_criteria=["Reference the evidence."],
        due_trigger="Before receiver completion.",
        source_node_id="source",
        target_node_id="receiver",
    )
    handoff.consume("receiver-output", "receiver")
    return handoff


def _audit(handoffs: list[Handoff]) -> dict:
    return reconcile_required_handoffs(
        session_id=SESSION,
        graph=_graph(),
        node_states={"source": "COMPLETE", "receiver": "COMPLETE"},
        outputs_by_node={
            "source": {"output_id": "source-output", "agent": "Source Agent"},
            "receiver": {"output_id": "receiver-output", "agent": "Receiver Agent"},
        },
        handoffs=handoffs,
    )


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["issues"]}


def _pending() -> Handoff:
    handoff = _handoff()
    handoff.status = "CREATED"
    handoff.receiving_output_id = ""
    handoff.receiving_node_id = ""
    handoff.consumed_at = ""
    handoff.resolution = "PENDING"
    return handoff


def _ack(handoff: Handoff, disposition: str = "ACCEPTED") -> dict:
    return {
        "handoff_id": handoff.handoff_id,
        "disposition": disposition,
        "requested_action_addressed": handoff.requested_action,
        "evidence_refs_addressed": list(handoff.evidence_refs),
        "acceptance_criteria_addressed": list(handoff.acceptance_criteria),
        "resolution_note": "Fixture resolution.",
    }


def test_valid_required_handoff_is_consumed_without_false_positive() -> None:
    report = _audit([_handoff()])
    assert report["status"] == "PASS"
    assert report["expected_required"] == report["consumed_required"] == 1
    assert report["issues"] == []
    assert report["unresolved"] == []


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "MISSING_HANDOFF"),
        ("duplicate", "DUPLICATE_HANDOFF"),
        ("stale", "STALE_HANDOFF"),
        ("wrong-recipient", "WRONG_RECIPIENT"),
        ("wrong-consumer", "WRONG_CONSUMER"),
        ("silently-dropped", "SILENTLY_DROPPED_HANDOFF"),
    ],
)
def test_fixed_handoff_mutation_catalog_fails_closed(
    mutation: str,
    expected_code: str,
) -> None:
    handoff = _handoff()
    records = [handoff]
    if mutation == "missing":
        records = []
    elif mutation == "duplicate":
        records.append(deepcopy(handoff))
    elif mutation == "stale":
        stale = deepcopy(handoff)
        stale.handoff_id = "seo-session-prior-risk-escalation-001"
        records.append(stale)
    elif mutation == "wrong-recipient":
        handoff.to_agent = "Unaddressed Agent"
    elif mutation == "wrong-consumer":
        handoff.receiving_output_id = "source-output"
    elif mutation == "silently-dropped":
        handoff.status = "CREATED"
        handoff.receiving_output_id = ""
        handoff.consumed_at = ""

    report = _audit(records)
    assert report["status"] == "FAIL"
    assert expected_code in _codes(report)
    if mutation == "silently-dropped":
        assert handoff.status == "BLOCKED"
        assert handoff.unresolved_reason
        assert report["unresolved"][0]["reason"]


def test_blocked_handoff_is_explicitly_reported_without_silent_drop_issue() -> None:
    handoff = _handoff()
    handoff.block("Receiver failed schema validation.")
    report = _audit([handoff])
    assert report["status"] == "FAIL"
    assert "SILENTLY_DROPPED_HANDOFF" not in _codes(report)
    assert report["unresolved"] == [
        {
            "handoff_id": HANDOFF_ID,
            "status": "BLOCKED",
            "reason": "Receiver failed schema validation.",
        }
    ]


@pytest.mark.parametrize(
    "mutation",
    ["partial-ref", "forged-ref", "wrong-action", "wrong-disposition", "wrong-node"],
)
def test_acknowledgement_contract_mutations_cannot_consume(mutation: str) -> None:
    handoff = _pending()
    handoff.evidence_refs = ["evidence-1", "evidence-2"]
    acknowledgement = _ack(handoff)
    node_id = "receiver"
    if mutation == "partial-ref":
        acknowledgement["evidence_refs_addressed"] = ["evidence-1"]
    elif mutation == "forged-ref":
        acknowledgement["evidence_refs_addressed"] = ["evidence-1", "foreign-evidence"]
    elif mutation == "wrong-action":
        acknowledgement["requested_action_addressed"] = "Perform unrelated work."
    elif mutation == "wrong-disposition":
        acknowledgement["disposition"] = "IGNORED"
    elif mutation == "wrong-node":
        node_id = "same-agent-other-node"
    resolve_handoff_acknowledgements(
        handoff,
        [acknowledgement],
        output_id="receiver-output",
        node_id=node_id,
    )
    assert handoff.status == "BLOCKED"
    assert handoff.resolution == "UNRESOLVED"
    assert handoff.unresolved_reason


def test_zero_evidence_control_handoff_supports_explicit_challenge() -> None:
    handoff = _pending()
    handoff.evidence_refs = []
    acknowledgement = _ack(handoff, "CHALLENGED")
    resolve_handoff_acknowledgements(
        handoff,
        [acknowledgement],
        output_id="receiver-output",
        node_id="receiver",
    )
    assert handoff.status == "CONSUMED"
    assert handoff.resolution == "CHALLENGED"
    assert handoff.receiving_node_id == "receiver"


def test_explicit_unresolved_ack_is_terminal_and_reasoned() -> None:
    handoff = _pending()
    acknowledgement = _ack(handoff, "UNRESOLVED")
    acknowledgement["resolution_note"] = "Required source is unavailable."
    resolve_handoff_acknowledgements(
        handoff,
        [acknowledgement],
        output_id="receiver-output",
        node_id="receiver",
    )
    assert handoff.status == "BLOCKED"
    assert handoff.resolution == "UNRESOLVED"
    assert handoff.unresolved_reason == "Required source is unavailable."


def test_vertical_capacity_exclusion_is_explicit_not_silently_truncated() -> None:
    session = SessionState.create(
        request="Run a complete SEO audit",
        mode="Audit",
        domain="https://example.com",
        business_type="ecommerce local international",
    )
    route = RouteResult(
        lead_agent="SEO Full Audit/Analyst Agent",
        supporting_agents=[],
        workflow="workflows/full-audit-workflow.md",
        required_evidence=[],
        confidence="High",
        escalation="fixture",
    )
    graph = build_workflow_graph(route, session)
    assert graph.capacity_exclusions == [
        {
            "agent": "International & Multilingual SEO Agent",
            "reason": "vertical specialist capacity is bounded to two agents",
            "status": "NOT_EXECUTED_CAPACITY",
        }
    ]
    assert graph.to_dict()["capacity_exclusions"] == graph.capacity_exclusions
