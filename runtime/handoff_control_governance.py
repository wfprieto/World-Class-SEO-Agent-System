"""Exact validation for runtime-declared non-dependency control handoffs."""
from __future__ import annotations

from typing import Any

from runtime.handoff_receipts import seal_terminal_handoff, terminal_receipt_is_valid
from runtime.state import Handoff


def audit_declared_controls(
    declarations: list[dict],
    by_id: dict[str, list[Handoff]],
    outputs_by_node: dict[str, dict[str, Any]],
) -> tuple[set[str], list[dict[str, str]]]:
    declared_ids: set[str] = set()
    issues: list[dict[str, str]] = []
    for declaration in declarations:
        contract = declaration.get("handoff", {})
        handoff_id = str(contract.get("handoff_id", "")) if isinstance(contract, dict) else ""
        if not _valid_declaration_shape(declaration, contract):
            issues.append(_issue("INVALID_CONTROL_DECLARATION", handoff_id))
            continue
        if not handoff_id or handoff_id in declared_ids:
            issues.append(_issue("INVALID_CONTROL_DECLARATION", handoff_id))
            continue
        declared_ids.add(handoff_id)
        matches = by_id.get(handoff_id, [])
        if not matches:
            issues.append(
                _issue("MISSING_CONTROL_HANDOFF", handoff_id)
            )
            continue
        issues.extend(_audit_control(contract, matches[0], outputs_by_node))
    return declared_ids, issues


def _valid_declaration_shape(declaration: dict, contract: object) -> bool:
    return (
        set(declaration) == {"control_type", "handoff"}
        and declaration.get("control_type") == "OPEN_RISK_ESCALATION"
        and isinstance(contract, dict)
    )


def _audit_control(
    contract: dict,
    handoff: Handoff,
    outputs_by_node: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    if handoff.control_contract() != contract:
        return [_issue("INVALID_CONTROL_HANDOFF", handoff.handoff_id)]
    if handoff.status == "CREATED":
        handoff.block("No exact acknowledgement resolved this declared control handoff.")
        seal_terminal_handoff(handoff)
        return [_issue("SILENTLY_DROPPED_HANDOFF", handoff.handoff_id)]
    receiver = outputs_by_node.get(handoff.target_node_id, {})
    if _wrong_consumer(handoff, receiver):
        return [_issue("WRONG_CONSUMER", handoff.handoff_id)]
    if not terminal_receipt_is_valid(handoff):
        return [_issue("INVALID_TERMINAL_RECEIPT", handoff.handoff_id)]
    return []


def _wrong_consumer(handoff: Handoff, receiver: dict[str, Any]) -> bool:
    context_bound = handoff.status == "CONSUMED" or (
        handoff.status == "BLOCKED" and bool(handoff.receiving_output_id)
    )
    return context_bound and (
        handoff.receiving_output_id != str(receiver.get("output_id", ""))
        or handoff.receiving_node_id != handoff.target_node_id
        or receiver.get("agent") != handoff.to_agent
    )


def _issue(code: str, handoff_id: str) -> dict[str, str]:
    details = {
        "INVALID_CONTROL_DECLARATION": "control declaration must be one unique exact OPEN_RISK_ESCALATION contract",
        "MISSING_CONTROL_HANDOFF": "declared control handoff was not materialized",
        "INVALID_CONTROL_HANDOFF": "materialized control does not exactly match its graph declaration",
        "SILENTLY_DROPPED_HANDOFF": "declared control was not exactly acknowledged",
        "WRONG_CONSUMER": "declared control terminal context does not match its target output",
        "INVALID_TERMINAL_RECEIPT": "declared control terminal fields do not match the resolver receipt",
    }
    return {"code": code, "handoff_id": handoff_id, "detail": details[code]}
