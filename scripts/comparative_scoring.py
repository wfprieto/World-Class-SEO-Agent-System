"""Versioned, deterministic comparative scorecard validation."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

MATURITY_MAX_SCORE = {
    "ABSENT": 1.9,
    "DOCUMENTED": 3.9,
    "STUB": 5.9,
    "FUNCTIONAL": 7.9,
    "LIVE_CAPABLE": 8.9,
    "PRODUCTION_READY": 9.5,
    "BEST_IN_CLASS": 10.0,
}
SCORE_MODEL_VERSION = "comparative-static-v1"
SCORE_FORMULA = "sum((score / 10) * weight)"
EXPECTED_CATEGORIES = (
    (1, "Agent Depth & Specialization", 10.0),
    (2, "Skill Coverage & Breadth", 10.0),
    (3, "Script & Execution Tooling", 15.0),
    (4, "Runtime Architecture & Governance", 15.0),
    (5, "Data Integrations & Live APIs", 10.0),
    (6, "Knowledge & Reference Depth", 10.0),
    (7, "Test Coverage & CI/CD", 10.0),
    (8, "Content Generation Capability", 5.0),
    (9, "Documentation & Onboarding", 10.0),
    (10, "Community, Maturity & Ecosystem", 5.0),
)
REVIEWED_SCORE_PROFILES = {
    "wfprieto/World-Class-SEO-Agent-System":
        (8.9, 7.0, 6.0, 10.0, 4.0, 6.0, 8.5, 6.0, 6.5, 4.0),
    "AgriciDaniel/claude-seo":
        (7.0, 9.0, 10.0, 4.0, 9.0, 9.0, 7.5, 8.0, 9.0, 9.0),
}


def weighted_score(scorecard: dict[str, Any]) -> float:
    return round(
        sum(
            (float(row["score"]) / 10.0) * float(row["weight"])
            for row in scorecard["categories"]
        ),
        4,
    )


def _evidence_digest(row: dict[str, Any]) -> str:
    material = {key: row[key] for key in ("source", "claim", "state")}
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _evidence_errors(category_id: object, evidence: object) -> tuple[list[str], list[str]]:
    if not isinstance(evidence, list) or not evidence:
        return [f"category {category_id} has no evidence"], []
    errors: list[str] = []
    identifiers: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            errors.append(f"category {category_id} evidence must be an object")
            continue
        evidence_id = str(item.get("id", ""))
        identifiers.append(evidence_id)
        if not evidence_id:
            errors.append(f"category {category_id} evidence has no id")
        if item.get("sha256") != _evidence_digest(item):
            errors.append(f"category {category_id} evidence digest mismatch: {evidence_id}")
    return errors, identifiers


def _category_errors(row: object) -> tuple[list[str], list[str]]:
    if not isinstance(row, dict):
        return ["every category must be an object"], []
    errors: list[str] = []
    category_id = row.get("id")
    maturity = str(row.get("evidence_maturity", ""))
    score = float(row.get("score", -1))
    if not math.isfinite(score):
        errors.append(f"category {category_id} score must be finite")
    elif maturity not in MATURITY_MAX_SCORE:
        errors.append(f"category {category_id} has unknown evidence maturity {maturity!r}")
    elif score > MATURITY_MAX_SCORE[maturity]:
        errors.append(
            f"category {category_id} score {score} exceeds maturity ceiling "
            f"{MATURITY_MAX_SCORE[maturity]} for {maturity}"
        )
    if score >= 8 and maturity not in {
        "LIVE_CAPABLE", "PRODUCTION_READY", "BEST_IN_CLASS"
    }:
        errors.append(f"category {category_id} cannot score 8+ without live-capable evidence")
    evidence_errors, evidence_ids = _evidence_errors(category_id, row.get("evidence"))
    return [*errors, *evidence_errors], evidence_ids


def _contract_errors(scorecard: dict[str, Any], categories: list[object]) -> list[str]:
    errors: list[str] = []
    if scorecard.get("score_model_version") != SCORE_MODEL_VERSION:
        errors.append(f"score_model_version must be {SCORE_MODEL_VERSION}")
    if scorecard.get("formula") != SCORE_FORMULA:
        errors.append("scorecard formula does not match the reviewed score model")
    rows = [row for row in categories if isinstance(row, dict)]
    raw_ids = [row.get("id") for row in rows]
    integer_ids = [item for item in raw_ids if isinstance(item, int)]
    if len(rows) != 10 or len(integer_ids) != 10 or sorted(integer_ids) != list(range(1, 11)):
        errors.append("category ids must be unique integers 1 through 10")
    weight = sum(float(row.get("weight", 0)) for row in rows)
    if abs(weight - 100.0) > 0.0001:
        errors.append(f"category weights must total 100; found {weight}")
    actual = tuple(
        (row.get("id"), row.get("name"), float(row.get("weight", 0))) for row in rows
    )
    if actual != EXPECTED_CATEGORIES:
        errors.append("category identities, order, names, or weights differ from the reviewed model")
    return errors


def _summary_errors(
    scorecard: dict[str, Any], categories: list[object], evidence_ids: list[str]
) -> list[str]:
    errors: list[str] = []
    calculated = weighted_score(scorecard)
    claimed = float(scorecard.get("overall_score", -1))
    if not math.isfinite(claimed):
        errors.append("overall_score must be finite")
    if abs(calculated - claimed) > 0.0001:
        errors.append(f"overall_score is {claimed}, but the formula produces {calculated}")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("evidence ids must be non-empty and unique")
    repository = str(scorecard.get("target_repository", "")).split("@", 1)[0]
    actual_scores = tuple(
        float(row.get("score", -1)) for row in categories if isinstance(row, dict)
    )
    if REVIEWED_SCORE_PROFILES.get(repository) != actual_scores:
        errors.append("category scores differ from the reviewed score profile")
    return errors


def validate_scorecard(scorecard: dict[str, Any]) -> list[str]:
    categories = scorecard.get("categories")
    if not isinstance(categories, list) or len(categories) != 10:
        return ["scorecard must contain exactly ten categories"]
    errors = _contract_errors(scorecard, categories)
    evidence_ids: list[str] = []
    for row in categories:
        row_errors, row_evidence_ids = _category_errors(row)
        errors.extend(row_errors)
        evidence_ids.extend(row_evidence_ids)
    return [*errors, *_summary_errors(scorecard, categories, evidence_ids)]
