"""Evidence layer for the canonical ``content-brief`` skill.

The website-relevance and observed-SERP gates are conservative kit governance
heuristics. They are not Google metrics, ranking factors, or ranking probabilities.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable
from urllib.parse import urlsplit

DEFAULT_WEIGHTS: dict[str, float] = {
    "intent_fit": 0.25,
    "first_hand_evidence": 0.20,
    "source_quality": 0.15,
    "freshness": 0.15,
    "entity_coverage": 0.15,
    "conversion_fit": 0.10,
}
_REQUIRED_CAPTURE = ("query", "locale", "device", "date", "source")
STALE_AFTER_DAYS = 30
_SITE_FIELDS = ("purpose", "audience", "offerings", "markets", "expertise")


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(
            character.lower() if character.isalnum() else " " for character in str(text)
        ).split()
        if len(token) > 2
    }


def _host(value: str) -> str:
    raw = str(value).strip()
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host: str, domain: str) -> bool:
    candidate = _host(domain)
    return bool(candidate) and (host == candidate or host.endswith("." + candidate))


def _weights(value: dict[str, float] | None) -> dict[str, float]:
    supplied = dict(DEFAULT_WEIGHTS if value is None else value)
    unknown = set(supplied) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown SERP heuristic weights: {sorted(unknown)}")
    if set(supplied) != set(DEFAULT_WEIGHTS):
        missing = set(DEFAULT_WEIGHTS) - set(supplied)
        raise ValueError(f"SERP heuristic weights missing: {sorted(missing)}")
    if any(not isinstance(item, (int, float)) or item < 0 for item in supplied.values()):
        raise ValueError("SERP heuristic weights must be non-negative numbers")
    total = float(sum(supplied.values()))
    if total <= 0:
        raise ValueError("SERP heuristic weights must sum to more than zero")
    return {key: float(item) / total for key, item in supplied.items()}


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
        reasons = ["Topic does not intersect the site's stated purpose, offerings, audience or expertise."]
        if search_volume:
            reasons.append("Search volume was supplied but is not a reason to publish an unrelated page.")
        return {
            "verdict": "NOT_RELEVANT",
            "reasons": reasons,
            "evidence": evidence,
            "conditions": [],
            "note": "Relevance is a kit governance gate, not a Google ranking factor.",
        }

    markets = [str(item).upper() for item in site.get("markets", [])]
    market_value = str(market or "").upper()
    market_ok = not market_value or not markets or any(
        market_value == item
        or market_value.startswith(item + "-")
        or item.startswith(market_value + "-")
        for item in markets
    )
    conditions: list[str] = []
    if not market_ok:
        conditions.append(f"Resolve market mismatch: requested {market}; site scope {markets}.")
    if not site.get("expertise"):
        conditions.append("Assign a credible first-hand expert or obtain substantiated proof.")
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


def _freshness(last_updated: str | None, as_of: str | None = None) -> float:
    if not last_updated:
        return 0.0
    try:
        updated = date.fromisoformat(str(last_updated)[:10])
        current = date.fromisoformat(str(as_of)[:10]) if as_of else date.today()
    except (TypeError, ValueError):
        return 0.0
    age_days = (current - updated).days
    return 1.0 if age_days <= 365 else 0.5 if age_days <= 1095 else 0.0


def _is_stale(captured: str | None, as_of: str | None = None) -> bool:
    if not captured:
        return True
    try:
        captured_date = date.fromisoformat(str(captured)[:10])
        current = date.fromisoformat(str(as_of)[:10]) if as_of else date.today()
    except (TypeError, ValueError):
        return True
    return (current - captured_date).days > STALE_AFTER_DAYS


def assess_serp(
    results: Iterable[dict[str, Any]],
    capture: dict[str, Any],
    own_domain: str,
    known_domain_competitors: list[str] | None = None,
    weights: dict[str, float] | None = None,
    as_of: str | None = None,
    target_intent: str | None = None,
) -> dict[str, Any]:
    missing = [key for key in _REQUIRED_CAPTURE if not capture.get(key)]
    if missing:
        raise ValueError(
            "SERP capture must record query, locale, device, date and source; missing: "
            + ", ".join(missing)
        )
    active_weights = _weights(weights)
    domain_competitors = {_host(item) for item in (known_domain_competitors or []) if _host(item)}
    own_host = _host(own_domain)
    stale = _is_stale(capture.get("date"), as_of)
    intents: set[str] = set()
    inaccessible: list[dict[str, Any]] = []
    seen: set[str] = set()
    competitors: list[dict[str, Any]] = []
    duplicates = 0
    own_results_excluded = 0

    for row in results or []:
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        normalized_url = url.rstrip("/")
        if normalized_url in seen:
            duplicates += 1
            continue
        seen.add(normalized_url)
        host = _host(url)
        if own_host and _domain_matches(host, own_host):
            own_results_excluded += 1
            continue
        if row.get("inaccessible") or row.get("fetch_error"):
            inaccessible.append({
                "url": url,
                "reason": str(row.get("fetch_error") or "marked inaccessible"),
                "evidence_state": "Not Run",
            })
            continue
        row_intent = str(row.get("intent", "")).strip().lower()
        if row_intent:
            intents.add(row_intent)
        kind = (
            "domain_and_serp"
            if any(_domain_matches(host, domain) for domain in domain_competitors)
            else "serp_only"
        )
        signals = {
            "intent_fit": (
                1.0
                if row_intent and (not target_intent or row_intent == target_intent.lower())
                else 0.0
            ),
            "first_hand_evidence": 1.0 if row.get("first_hand_evidence") else 0.0,
            "source_quality": 1.0 if row.get("sources_cited") else 0.0,
            "freshness": _freshness(row.get("last_updated"), as_of),
            "entity_coverage": min(len(row.get("entities") or []) / 3.0, 1.0),
            "conversion_fit": 1.0 if row.get("conversion_path") else 0.0,
        }
        observed = {
            key: value
            for key, value in row.items()
            if key in ("url", "position", "page_type", "intent", "last_updated", "entities")
        }
        heuristic = round(
            sum(signals[key] * active_weights[key] for key in signals) * 100,
            1,
        )
        competitors.append({
            "url": url,
            "competitor_kind": kind,
            "observed": observed,
            "signals": signals,
            "heuristic_score": heuristic,
            "inference_note": "Signals are inferred from supplied fields, not measured by Google.",
        })

    if not competitors:
        reason = (
            "Search results were supplied but none were readable competitor pages."
            if inaccessible or own_results_excluded
            else "No search results were supplied for this query, locale and device."
        )
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "capture": capture,
            "competitors": [],
            "result_count": 0,
            "duplicates_removed": duplicates,
            "own_results_excluded": own_results_excluded,
            "inaccessible": inaccessible,
            "stale": stale,
            "mixed_intent": False,
            "score_basis": "kit_heuristic",
            "weights_configurable": True,
            "weights": active_weights,
            "disclaimer": "Heuristic only. This is not a Google score and not a ranking probability.",
            "missing_evidence": [reason],
        }

    mixed_intent = len(intents) > 1
    return {
        "status": "STALE_EVIDENCE" if stale else "OK",
        "stale": stale,
        "mixed_intent": mixed_intent,
        "intent_note": (
            "The observed results serve more than one intent. Select and state one target intent before briefing."
            if mixed_intent
            else "Observed results share one dominant intent."
        ),
        "inaccessible": inaccessible,
        "capture": capture,
        "own_domain": own_domain,
        "own_results_excluded": own_results_excluded,
        "target_intent": target_intent,
        "result_count": len(competitors),
        "duplicates_removed": duplicates,
        "competitors": competitors,
        "bar_to_beat": max(item["heuristic_score"] for item in competitors),
        "score_basis": "kit_heuristic",
        "weights_configurable": True,
        "weights": active_weights,
        "disclaimer": (
            "Heuristic only. This is not a Google score, ranking factor, or probability of ranking. "
            "Direct observation is separated from inference."
        ),
        "missing_evidence": [],
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
    if verdict == "CONDITIONALLY_RELEVANT" and not conditions_resolved:
        return {
            "publish": False,
            "reason": "Website relevance is conditional and the stated conditions are unresolved.",
            "conditions": relevance.get("conditions", []),
        }
    if serp.get("status") in {"INSUFFICIENT_EVIDENCE", "STALE_EVIDENCE"}:
        return {
            "publish": False,
            "reason": f"SERP evidence status is {serp.get('status')}; refresh or supply evidence.",
        }
    if serp.get("mixed_intent") and not selected_intent:
        return {
            "publish": False,
            "reason": "Mixed-intent SERP requires one explicitly selected target intent.",
        }
    if not information_gain:
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
