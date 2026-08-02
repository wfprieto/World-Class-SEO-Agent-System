"""Deterministic, bounded evidence identity and material-claim validation.

This module proves internal references and declared evidence states are coherent.
It does not prove that an external source is truthful, complete, or current.
"""

from __future__ import annotations

import copy
import re
from pathlib import PurePath
from typing import Any

_URL = re.compile(r"https?://[^\s)\]>\"']+")
_NUMBER = re.compile(r"(?<![A-Za-z0-9])(?:\$?\d+(?:[.,]\d+)*(?:%|x)?)(?![A-Za-z0-9])")
_CURRENT_CONTRACT = "2.0.0"
_LEGACY_CONTRACT = "1.0.0"
_EXECUTION_STATES = {"COMPLETE", "PARTIAL", "BLOCKED", "FAILED", "SYNTHETIC"}
_EVIDENCE_TO_CLAIM_STATE = {
    "CURRENT": "AVAILABLE",
    "UNVERIFIED": "PARTIAL",
    "STALE": "STALE",
    "MISSING": "MISSING",
    "INVALID": "INVALID",
    "CONTRADICTORY": "BLOCKED",
}
_CLAIM_STATE_STRENGTH = {
    "AVAILABLE": 0,
    "PARTIAL": 1,
    "STALE": 2,
    "MISSING": 3,
    "INVALID": 4,
    "BLOCKED": 5,
}


def _material_texts(output: dict[str, Any]) -> list[str]:
    values = [
        str(output.get("summary", "")),
        str(output.get("impact", "")),
        str(output.get("follow_up", "")),
    ]
    values.extend(
        str(item)
        for field in ("risks", "dependencies", "acceptance_criteria", "verification")
        for item in output.get(field, [])
    )
    values.extend(
        " ".join((str(item.get("finding", "")), str(item.get("affected_scope", ""))))
        for item in output.get("findings", [])
        if isinstance(item, dict)
    )
    values.extend(
        " ".join((str(item.get("action", "")), str(item.get("success_metric", ""))))
        for item in output.get("recommended_actions", [])
        if isinstance(item, dict)
    )
    return values


def _rewrite_refs(rows: Any, aliases: dict[str, str]) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_refs"), list):
            continue
        row["evidence_refs"] = [aliases.get(str(ref), str(ref)) for ref in row["evidence_refs"]]


def normalize_legacy_output(output: dict[str, Any]) -> dict[str, Any]:
    """Opt in to legacy parsing while forcing PARTIAL and UNVERIFIED semantics."""
    if output.get("contract_version") is not None:
        raise ValueError("legacy normalization requires an unversioned output")
    normalized = copy.deepcopy(output)
    aliases_by_value: dict[str, list[str]] = {}
    evidence = normalized.get("evidence", [])
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            evidence_id = str(item.get("id") or source or f"legacy-evidence-{index + 1}")
            item["id"] = evidence_id
            item["state"] = "UNVERIFIED"
            for alias in {evidence_id, source, PurePath(source).name if source else ""} - {""}:
                aliases_by_value.setdefault(alias, []).append(evidence_id)
    aliases = {
        alias: identities[0]
        for alias, identities in aliases_by_value.items()
        if len(set(identities)) == 1
    }
    _rewrite_refs(normalized.get("findings"), aliases)
    _rewrite_refs(normalized.get("material_claims"), aliases)
    claims = normalized.get("material_claims")
    if not isinstance(claims, list):
        claims = []
        normalized["material_claims"] = claims
    for claim in claims:
        if isinstance(claim, dict):
            claim["evidence_state"] = "PARTIAL"
    normalized.update(
        {
            "contract_version": _LEGACY_CONTRACT,
            "execution_state": "PARTIAL",
            "legacy_unverified": True,
        }
    )
    return normalized


def _contract_errors(output: dict[str, Any]) -> tuple[list[str], bool]:
    version = output.get("contract_version")
    errors: list[str] = []
    if version not in {_CURRENT_CONTRACT, _LEGACY_CONTRACT}:
        errors.append(
            "contract_version is required; legacy input must use explicit normalization"
        )
        return errors, False
    legacy = version == _LEGACY_CONTRACT
    if "execution_state" not in output:
        errors.append("execution_state is required")
    elif output.get("execution_state") not in _EXECUTION_STATES:
        errors.append("execution_state is invalid")
    if "material_claims" not in output:
        errors.append("material_claims is required")
    if legacy and (
        output.get("execution_state") != "PARTIAL"
        or output.get("legacy_unverified") is not True
    ):
        errors.append("legacy output must be explicitly PARTIAL and legacy_unverified")
    if not legacy and "legacy_unverified" in output:
        errors.append("current output cannot claim legacy_unverified semantics")
    return errors, legacy


def _evidence_inventory(
    output: dict[str, Any], *, legacy: bool
) -> tuple[dict[str, str], list[str]]:
    inventory: dict[str, str] = {}
    sources: set[str] = set()
    errors: list[str] = []
    evidence = output.get("evidence", [])
    if not isinstance(evidence, list):
        return {}, ["evidence must be a list"]
    for index, item in enumerate(evidence):
        prefix = f"evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        evidence_id = str(item.get("id", "")).strip()
        source = str(item.get("source", "")).strip()
        state = str(item.get("state", "")).upper()
        if not evidence_id:
            errors.append(f"{prefix}.id is required")
        elif evidence_id in inventory:
            errors.append(f"duplicate evidence id: {evidence_id}")
        else:
            inventory[evidence_id] = state
        if not source:
            errors.append(f"{prefix}.source is required")
        elif source in sources:
            errors.append(f"duplicate evidence source: {source}")
        sources.add(source)
        errors.extend(_evidence_state_errors(prefix, state, legacy=legacy))
    return inventory, errors


def _evidence_state_errors(prefix: str, state: str, *, legacy: bool) -> list[str]:
    if state not in _EVIDENCE_TO_CLAIM_STATE:
        return [f"{prefix}.state is invalid"]
    if legacy and state != "UNVERIFIED":
        return [f"{prefix} legacy evidence must be UNVERIFIED"]
    if not legacy and state == "UNVERIFIED":
        return [f"{prefix} current evidence cannot be UNVERIFIED"]
    return []


def _finding_errors(output: dict[str, Any], evidence_ids: set[str]) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    finding_ids: set[str] = set()
    findings = output.get("findings", [])
    if not isinstance(findings, list):
        return ["findings must be a list"], finding_ids
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id", "")).strip()
        if not finding_id:
            errors.append(f"findings[{index}].id is required")
        elif finding_id in finding_ids:
            errors.append(f"duplicate finding id: {finding_id}")
        finding_ids.add(finding_id)
        refs = finding.get("evidence_refs", [])
        if not isinstance(refs, list) or not refs:
            errors.append(f"finding {finding_id or index} has no evidence_refs")
            continue
        normalized = [str(ref) for ref in refs]
        if len(normalized) != len(set(normalized)):
            errors.append(f"finding {finding_id or index} repeats evidence reference")
        errors.extend(
            f"finding {finding_id or index} references unknown evidence: {ref}"
            for ref in sorted(set(normalized) - evidence_ids)
        )
    return errors, finding_ids


def _claim_state_error(
    prefix: str, claim_state: str, refs: list[str], inventory: dict[str, str]
) -> str | None:
    known_states = [
        inventory[ref]
        for ref in refs
        if ref in inventory and inventory[ref] in _EVIDENCE_TO_CLAIM_STATE
    ]
    if not known_states or claim_state not in _CLAIM_STATE_STRENGTH:
        return None
    required = max(
        (_EVIDENCE_TO_CLAIM_STATE[state] for state in known_states),
        key=_CLAIM_STATE_STRENGTH.__getitem__,
    )
    if _CLAIM_STATE_STRENGTH[claim_state] < _CLAIM_STATE_STRENGTH[required]:
        return f"{prefix} evidence_state {claim_state} is stronger than referenced evidence state {required}"
    return None


def _claim_errors(
    output: dict[str, Any], inventory: dict[str, str], identity_ids: set[str]
) -> tuple[list[str], str]:
    errors: list[str] = []
    statements: list[str] = []
    claims = output.get("material_claims", [])
    if not isinstance(claims, list):
        return ["material_claims must be a list"], ""
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"material_claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        claim_id = str(claim.get("claim_id", "")).strip()
        errors.extend(_claim_identity_errors(prefix, claim_id, seen, identity_ids))
        seen.add(claim_id)
        statements.append(str(claim.get("statement", "")))
        refs_value = claim.get("evidence_refs", [])
        refs = [str(ref) for ref in refs_value] if isinstance(refs_value, list) else []
        errors.extend(_claim_reference_errors(prefix, refs, set(inventory)))
        state = str(claim.get("evidence_state", ""))
        if state not in _CLAIM_STATE_STRENGTH:
            errors.append(f"{prefix}.evidence_state is invalid")
        contradiction = _claim_state_error(prefix, state, refs, inventory)
        if contradiction:
            errors.append(contradiction)
        if not bool(claim.get("inference", False)) and state in {
            "MISSING",
            "INVALID",
            "BLOCKED",
        }:
            errors.append(f"{prefix} presents unavailable evidence state {state} as fact")
    return errors, "\n".join(statements)


def _claim_identity_errors(
    prefix: str, claim_id: str, seen: set[str], identity_ids: set[str]
) -> list[str]:
    if not claim_id:
        return [f"{prefix}.claim_id is required"]
    if claim_id in seen:
        return [f"duplicate material claim id: {claim_id}"]
    if claim_id in identity_ids:
        return [f"material claim identity collides with evidence or finding: {claim_id}"]
    return []


def _claim_reference_errors(
    prefix: str, refs: list[str], evidence_ids: set[str]
) -> list[str]:
    errors = [] if refs else [f"{prefix} has no evidence_refs"]
    if len(refs) != len(set(refs)):
        errors.append(f"{prefix} repeats evidence reference")
    errors.extend(
        f"{prefix} references unknown evidence: {ref}"
        for ref in sorted(set(refs) - evidence_ids)
    )
    return errors


def _unbound_material_errors(output: dict[str, Any], claim_text: str) -> list[str]:
    tokens: set[str] = set()
    for text in _material_texts(output):
        tokens.update(_URL.findall(text))
        tokens.update(_NUMBER.findall(text))
    return [
        f"material value or URL is not bound to a material_claim: {token}"
        for token in sorted(tokens)
        if token not in claim_text
    ]


def validate_evidence_binding(output: dict[str, Any]) -> list[str]:
    """Validate bounded identity, reference, state, and material-token coherence."""
    errors, legacy = _contract_errors(output)
    inventory, evidence_errors = _evidence_inventory(output, legacy=legacy)
    errors.extend(evidence_errors)
    finding_errors, finding_ids = _finding_errors(output, set(inventory))
    errors.extend(finding_errors)
    collisions = set(inventory) & finding_ids
    errors.extend(
        f"evidence and finding identities collide: {identity}"
        for identity in sorted(collisions)
    )
    claim_errors, claim_text = _claim_errors(
        output, inventory, set(inventory) | finding_ids
    )
    errors.extend(claim_errors)
    if not legacy and output.get("execution_state") in {"COMPLETE", "PARTIAL"}:
        errors.extend(_unbound_material_errors(output, claim_text))
    return sorted(set(errors))
