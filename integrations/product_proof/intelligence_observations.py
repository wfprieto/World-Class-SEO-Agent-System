"""Offline-safe SEO intelligence analyzers derived from the governed source corpus."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from contracts.adapter import AdapterResult
from integrations.product_proof.intelligence_io import _read_json


def _normalized_observations(rows: list[object], required: set[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            errors.append(f"observation {index} must be an object")
            continue
        missing = sorted(required - set(raw))
        if missing:
            errors.append(f"observation {index} missing: {', '.join(missing)}")
            continue
        try:
            position = (
                float(raw["organic_position"]) if raw["organic_position"] is not None else None
            )
        except (TypeError, ValueError):
            errors.append(f"observation {index} organic_position must be numeric or null")
            continue
        normalized.append(
            {
                "observed_at": str(raw["observed_at"]),
                "platform": str(raw["platform"]),
                "prompt": str(raw["prompt"]),
                "aio_present": bool(raw["aio_present"]),
                "organic_position": position,
                "cited": bool(raw["cited"]),
                "citation_order": raw.get("citation_order"),
                "recommendation_state": str(raw.get("recommendation_state", "UNKNOWN")),
                "linked": bool(raw.get("linked", False)),
                "destination_url": raw.get("destination_url"),
                "narrative_accuracy": str(raw.get("narrative_accuracy", "NOT_REVIEWED")),
                "source_mix": str(raw.get("source_mix", "UNKNOWN")),
                "competitors_cited": [str(item) for item in raw.get("competitors_cited", [])],
                "evidence_source": str(raw.get("evidence_source", "operator_observation")),
            }
        )
    if errors:
        raise ValueError("; ".join(errors[:20]))
    return normalized


def _opportunity_groups(normalized: list[dict[str, Any]]) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
    list[dict[str, Any]], list[dict[str, Any]],
]:
    opportunities = [
        row
        for row in normalized
        if row["aio_present"]
        and row["organic_position"] is not None
        and row["organic_position"] <= 10
        and not row["cited"]
    ]
    inaccurate = [
        row for row in normalized if row["narrative_accuracy"] in {"INACCURATE", "MISLEADING"}
    ]
    cited = [row for row in normalized if row["cited"]]
    recommended = [row for row in cited if row["recommendation_state"] == "RECOMMENDED"]
    linked = [row for row in cited if row["linked"]]
    return opportunities, inaccurate, cited, recommended, linked


class AICitationOpportunityAnalyzer:
    name = "ai_citation_opportunity"
    REQUIRED = {"observed_at", "platform", "prompt", "aio_present", "organic_position", "cited"}

    def analyze(self, *, observations_path: str | Path) -> AdapterResult:
        payload = _read_json(observations_path)
        rows = payload.get("observations", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("observations must be a list or an object containing observations")
        normalized = _normalized_observations(rows, self.REQUIRED)
        opportunities, inaccurate, cited, recommended, linked = _opportunity_groups(normalized)
        data = {
            "operation": "ai_citation_opportunities",
            "observation_count": len(normalized),
            "platforms": dict(sorted(Counter(row["platform"] for row in normalized).items())),
            "prompt_coverage": round(len(cited) / len(normalized), 4) if normalized else None,
            "recommendation_rate": round(len(recommended) / len(normalized), 4)
            if normalized
            else None,
            "linked_citation_rate": round(len(linked) / len(cited), 4) if cited else None,
            "unowned_ai_overview_opportunities": opportunities,
            "unowned_count": len(opportunities),
            "representation_risks": inaccurate,
            "representation_risk_count": len(inaccurate),
            "observed": normalized,
            "evidence_layer": "OBSERVED",
            "limitations": [
                "Results are dated snapshots and can vary by account, location, device, prompt wording, and platform state.",
                "Organic position and AI citation are separate observations; one does not prove the cause of the other.",
                "No modeled reach or revenue is blended into these observed metrics.",
            ],
        }
        return AdapterResult(
            self.name,
            "ok" if normalized else "empty",
            data,
            [] if normalized else ["No dated observations were supplied."],
        )
