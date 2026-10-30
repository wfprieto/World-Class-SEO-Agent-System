"""Validation for optional entity-analysis provider receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _approved_cost(payload: dict[str, Any]) -> dict[str, float | str]:
    approval = payload.get("cost_approval")
    if not isinstance(approval, dict) or approval.get("state") != "APPROVED":
        raise ValueError("provider_analysis requires an approved cost gate")
    estimated, ceiling = approval.get("estimated_cost"), approval.get("approved_ceiling")
    if not isinstance(estimated, (int, float)) or isinstance(estimated, bool):
        raise ValueError("provider_analysis requires a valid approved cost gate")
    if not isinstance(ceiling, (int, float)) or isinstance(ceiling, bool):
        raise ValueError("provider_analysis requires a valid approved cost gate")
    if float(estimated) < 0 or float(ceiling) < float(estimated):
        raise ValueError("provider_analysis requires a valid approved cost gate")
    return {
        "state": "APPROVED",
        "estimated_cost": float(estimated),
        "approved_ceiling": float(ceiling),
    }


def _entity(row: object, seen: set[str]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("every provider entity must be an object")
    entity_id = _required_text(row, "id")
    if entity_id in seen:
        raise ValueError(f"duplicate provider entity id: {entity_id}")
    seen.add(entity_id)
    salience = row.get("salience")
    if not isinstance(salience, (int, float)) or isinstance(salience, bool):
        raise ValueError(f"provider entity {entity_id} salience must be from 0 to 1")
    if not 0 <= float(salience) <= 1:
        raise ValueError(f"provider entity {entity_id} salience must be from 0 to 1")
    return {
        "id": entity_id,
        "name": _required_text(row, "name"),
        "type": _required_text(row, "type"),
        "salience": float(salience),
        "evidence_state": "SUPPLIED_PROVIDER_EVIDENCE",
    }


def normalize_entity_analysis(
    payload: dict[str, Any] | None, *, provider_state: str
) -> dict[str, Any]:
    """Normalize supplied evidence without claiming that this repository called the provider."""
    if payload is None:
        return {
            "state": "NOT_RUN",
            "provider": None,
            "entities": [],
            "provenance": None,
            "limitations": ["No optional provider analysis was supplied."],
        }
    if not isinstance(payload, dict):
        raise TypeError("provider_analysis must be an object")
    provider = _required_text(payload, "provider")
    if provider != "entity-analysis" or provider_state != "AVAILABLE":
        raise ValueError("entity-analysis provider credentials are not configured")
    captured_at = _required_text(payload, "captured_at")
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at must be an ISO timestamp") from exc
    rows = payload.get("entities")
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("provider entities must be an array with at most 500 rows")
    seen: set[str] = set()
    return {
        "state": "SUPPLIED_PROVIDER_EVIDENCE",
        "provider": provider,
        "entities": [_entity(row, seen) for row in rows],
        "cost_approval": _approved_cost(payload),
        "provenance": {"source": _required_text(payload, "source"), "captured_at": captured_at},
        "limitations": [
            "The repository normalized supplied provider output; it did not execute the provider call.",
            "Provider salience and type remain observations, not independent factual verification.",
        ],
    }
