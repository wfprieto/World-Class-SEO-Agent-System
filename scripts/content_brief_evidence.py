"""Evidence layer for the canonical ``content-brief`` skill.

The website-relevance and observed-SERP gates are conservative kit governance
heuristics. They are not Google metrics, ranking factors, or ranking probabilities.
"""

from __future__ import annotations

from typing import Any

from scripts.content_brief_validation import (
    relevance_evidence_valid,
    serp_evidence_valid,
    text_rows,
)
from scripts.content_serp_observations import (
    _REQUIRED_CAPTURE,
)
from scripts.content_serp_observations import (
    DEFAULT_WEIGHTS as DEFAULT_WEIGHTS,
)
from scripts.content_serp_observations import (
    STALE_AFTER_DAYS as STALE_AFTER_DAYS,
)
from scripts.content_serp_observations import (
    _domain_matches as _domain_matches,
)
from scripts.content_serp_observations import (
    _host as _host,
)
from scripts.content_serp_observations import (
    _is_stale as _is_stale,
)
from scripts.content_serp_observations import (
    _weights as _weights,
)
from scripts.content_serp_observations import (
    assess_serp as assess_serp,
)

_SITE_FIELDS = ("purpose", "audience", "offerings", "markets", "expertise")


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(
            character.lower() if character.isalnum() else " " for character in str(text)
        ).split()
        if len(token) > 2
    }


def _market_conditions(site: dict[str, Any], market: str | None) -> list[str]:
    markets = [str(item).upper() for item in site.get("markets", [])]
    market_value = str(market or "").upper()
    market_ok = (
        not market_value
        or not markets
        or any(
            market_value == item
            or market_value.startswith(item + "-")
            or item.startswith(market_value + "-")
            for item in markets
        )
    )
    conditions: list[str] = []
    if not market_ok:
        conditions.append(f"Resolve market mismatch: requested {market}; site scope {markets}.")
    if not site.get("expertise"):
        conditions.append("Assign a credible first-hand expert or obtain substantiated proof.")
    return conditions


def assess_relevance(
    site: dict[str, Any],
    topic: str,
    market: str | None = None,
    search_volume: int | None = None,
) -> dict[str, Any]:
    known = [field for field in _SITE_FIELDS if site.get(field)]
    if len(known) < 3:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reasons": ["Site purpose, audience, offerings, markets, or expertise not supplied."],
            "evidence": {"site_fields_supplied": known},
            "conditions": [],
            "note": "Relevance is a kit governance gate, not a Google ranking factor.",
        }

    topic_tokens = _tokens(topic)
    corpus = _tokens(
        " ".join(
            [str(site.get("purpose", "")), str(site.get("audience", ""))]
            + [str(item) for item in site.get("offerings", [])]
            + [str(item) for item in site.get("expertise", [])]
            + [str(item) for item in site.get("existing_topics", [])]
        )
    )
    overlap = topic_tokens & corpus
    evidence = {
        "topic_tokens": sorted(topic_tokens),
        "matched_site_tokens": sorted(overlap),
        "site_fields_supplied": known,
    }
    if not overlap:
        reasons = [
            "Topic does not intersect the site's stated purpose, offerings, audience or expertise."
        ]
        if search_volume:
            reasons.append(
                "Search volume was supplied but is not a reason to publish an unrelated page."
            )
        return {
            "verdict": "NOT_RELEVANT",
            "reasons": reasons,
            "evidence": evidence,
            "conditions": [],
            "note": "Relevance is a kit governance gate, not a Google ranking factor.",
        }

    conditions = _market_conditions(site, market)
    if conditions:
        return {
            "verdict": "CONDITIONALLY_RELEVANT",
            "reasons": conditions,
            "conditions": conditions,
            "evidence": evidence,
            "note": "Relevance is a kit governance gate, not a Google ranking factor.",
        }
    return {
        "verdict": "RELEVANT",
        "reasons": ["Topic intersects the site's purpose, offerings and expertise, in-market."],
        "conditions": [],
        "evidence": evidence,
        "note": "Relevance is a kit governance gate, not a Google ranking factor.",
    }


def brief_decision(
    relevance: dict[str, Any],
    serp: dict[str, Any],
    information_gain: list[str],
    *,
    conditions_resolved: bool = False,
    selected_intent: str | None = None,
) -> dict[str, Any]:
    verdict = relevance.get("verdict")
    if verdict == "NOT_RELEVANT":
        return {"publish": False, "reason": "Website-relevance gate returned NOT_RELEVANT."}
    if verdict == "INSUFFICIENT_EVIDENCE":
        return {"publish": False, "reason": "Insufficient site evidence to judge relevance."}
    if verdict == "CONDITIONALLY_RELEVANT" and conditions_resolved is not True:
        return {
            "publish": False,
            "reason": "Website relevance is conditional and the stated conditions are unresolved.",
            "conditions": relevance.get("conditions", []),
        }
    if verdict not in {"RELEVANT", "CONDITIONALLY_RELEVANT"}:
        return {"publish": False, "reason": "Positive website-relevance evidence is required."}
    if serp.get("status") != "OK":
        return {
            "publish": False,
            "reason": f"SERP evidence status is {serp.get('status')}; refresh or supply evidence.",
        }
    if not relevance_evidence_valid(relevance, _SITE_FIELDS):
        return {
            "publish": False,
            "reason": "Relevance assessment is missing supported producer evidence.",
        }
    if not serp_evidence_valid(serp, _REQUIRED_CAPTURE, STALE_AFTER_DAYS, tuple(DEFAULT_WEIGHTS)):
        return {
            "publish": False,
            "reason": "SERP assessment requires coherent observations and a current capture.",
        }
    if serp.get("mixed_intent") and not selected_intent:
        return {
            "publish": False,
            "reason": "Mixed-intent SERP requires one explicitly selected target intent.",
        }
    if not text_rows(information_gain):
        return {
            "publish": False,
            "reason": "No distinct information gain stated. A brief must add value beyond observed results.",
        }
    return {
        "publish": True,
        "reason": "Relevance and current SERP evidence pass, with stated information gain.",
        "must_beat": serp.get("bar_to_beat"),
        "selected_intent": selected_intent or serp.get("target_intent"),
        "information_gain": information_gain,
    }
