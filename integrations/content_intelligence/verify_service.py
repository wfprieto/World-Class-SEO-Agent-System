"""Deterministic content intelligence with explicit truth boundaries.

The service measures supplied text and supplied review records. It does not
claim Google ranking potential, originality, factual accuracy, expertise,
source existence, user satisfaction, or causal explanations that were not
independently established.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from contracts.adapter import AdapterResult
from integrations.content_intelligence.analysis import (
    bounded_records,
    iso_date,
    require_unique_ids,
    required_string,
    safe_registry_url,
)

_ALLOWED_RELATIONS = {"supports", "contradicts", "partial", "context_only", "not_checked"}


def verify(
    name: str,
    *,
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    **_: Any,
) -> AdapterResult:
    claim_rows = bounded_records(claims, "claims")
    source_rows = bounded_records(sources, "sources")
    require_unique_ids(claim_rows, "claim")
    require_unique_ids(source_rows, "source")
    source_map, normalized_sources = _source_register(source_rows)

    normalized_claims: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    warnings: list[str] = []
    for claim in claim_rows:
        claim_id = required_string(claim, "id", "claim")
        text = required_string(claim, "text", f"claim {claim_id}")
        source_ids = [
            str(item).strip() for item in claim.get("source_ids", []) if str(item).strip()
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(f"claim {claim_id} contains duplicate source_ids")
        missing_sources = sorted(
            source_id for source_id in source_ids if source_id not in source_map
        )
        normalized_assessments, valid_relations, assessment_issues = _assessments(
            claim, claim_id, source_ids, source_map
        )
        state = _claim_state(missing_sources, source_ids, valid_relations)
        state_counts[state] += 1
        normalized_claims.append(
            {
                "id": claim_id,
                "text": text,
                "source_ids": source_ids,
                "missing_source_ids": missing_sources,
                "source_assessments": normalized_assessments,
                "assessment_issues": assessment_issues,
                "verification_state": state,
                "verification_basis": "SUPPLIED_HUMAN_REVIEW_RECORDS_ONLY",
            }
        )
        if state != "SUPPORTED_BY_SUPPLIED_REVIEW":
            warnings.append(f"Claim {claim_id} remains {state}.")
        warnings.extend(f"Claim {claim_id}: {issue}." for issue in assessment_issues)
    unresolved, contradicted, status = _verification_summary(state_counts)
    return AdapterResult(
        source=name,
        status=status,
        data={
            "operation": "verify",
            "data_state": "AVAILABLE" if status == "ok" else "PARTIAL",
            "claims": normalized_claims,
            "sources": normalized_sources,
            "summary": {
                "claim_count": len(normalized_claims),
                "source_count": len(normalized_sources),
                "states": dict(sorted(state_counts.items())),
                "unsupported_or_unverified": unresolved,
                "contradicted": contradicted,
            },
            "independent_source_fetch": "NOT_RUN",
            "semantic_source_validation": "SUPPLIED_REVIEW_ONLY",
            "limitations": [
                "A URL, citation, or source title alone does not verify a claim.",
                "The service validates supplied review records but does not independently read or authenticate sources.",
            ],
        },
        warnings=warnings,
    )


def _source_register(
    source_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    source_map: dict[str, dict[str, Any]] = {}
    normalized_sources: list[dict[str, Any]] = []
    for source in source_rows:
        source_id = required_string(source, "id", "source")
        title = required_string(source, "title", f"source {source_id}")
        url = source.get("url")
        if url is not None:
            safe_registry_url(str(url))
        row = {
            "id": source_id,
            "title": title,
            "url": str(url) if url else None,
            "publisher": source.get("publisher"),
            "primary": bool(source.get("primary", False)),
            "published_at": source.get("published_at"),
            "accessed_at": source.get("accessed_at"),
            "source_quality": "OPERATOR_SUPPLIED",
            "availability": "NOT_CHECKED",
        }
        for key in ("published_at", "accessed_at"):
            if row[key]:
                iso_date(str(row[key]), f"source {source_id} {key}")
        source_map[source_id] = row
        normalized_sources.append(row)

    return source_map, normalized_sources


def _assessments(
    claim: dict[str, Any],
    claim_id: str,
    source_ids: list[str],
    source_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    assessments = bounded_records(
        claim.get("source_assessments", []), f"claim {claim_id} source_assessments"
    )
    normalized_assessments: list[dict[str, Any]] = []
    valid_relations: list[str] = []
    assessment_issues: list[str] = []
    for assessment in assessments:
        source_id = required_string(assessment, "source_id", f"claim {claim_id} assessment")
        relation = required_string(assessment, "relation", f"claim {claim_id} assessment").lower()
        if relation not in _ALLOWED_RELATIONS:
            raise ValueError(
                f"claim {claim_id} assessment relation must be one of {sorted(_ALLOWED_RELATIONS)}"
            )
        reviewer = str(assessment.get("reviewer") or "").strip()
        reviewed_at = str(assessment.get("reviewed_at") or "").strip()
        if source_id not in source_ids:
            assessment_issues.append(f"assessment references undeclared source {source_id}")
        if source_id not in source_map:
            assessment_issues.append(f"assessment references missing source {source_id}")
        review_complete = bool(reviewer and reviewed_at)
        if reviewed_at:
            iso_date(reviewed_at, f"claim {claim_id} reviewed_at")
        if not review_complete:
            assessment_issues.append(
                f"assessment for source {source_id} lacks reviewer or reviewed_at"
            )
        if review_complete and source_id in source_map and source_id in source_ids:
            valid_relations.append(relation)
        normalized_assessments.append(
            {
                "source_id": source_id,
                "relation": relation,
                "reviewer": reviewer or None,
                "reviewed_at": reviewed_at or None,
                "note": assessment.get("note"),
                "review_complete": review_complete,
            }
        )

    return normalized_assessments, valid_relations, assessment_issues


def _claim_state(
    missing_sources: list[str], source_ids: list[str], valid_relations: list[str]
) -> str:
    if missing_sources:
        state = "SOURCE_MISSING"
    elif not source_ids:
        state = "UNSUPPORTED"
    elif "contradicts" in valid_relations:
        state = "CONTRADICTED_BY_SUPPLIED_REVIEW"
    elif "supports" in valid_relations:
        state = "SUPPORTED_BY_SUPPLIED_REVIEW"
    elif "partial" in valid_relations:
        state = "PARTIALLY_SUPPORTED_BY_SUPPLIED_REVIEW"
    else:
        state = "UNVERIFIED"

    return state



def _verification_summary(state_counts: Counter[str]) -> tuple[int, int, str]:
    unresolved_states = {
        "SOURCE_MISSING",
        "UNSUPPORTED",
        "UNVERIFIED",
        "PARTIALLY_SUPPORTED_BY_SUPPLIED_REVIEW",
    }
    unresolved = sum(state_counts[state] for state in unresolved_states)
    contradicted = state_counts["CONTRADICTED_BY_SUPPLIED_REVIEW"]
    status = "ok" if unresolved == 0 and contradicted == 0 else "needs-review"

    return unresolved, contradicted, status
