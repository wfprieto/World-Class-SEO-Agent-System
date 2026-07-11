"""Evidence layer for the canonical `content-brief` skill.

Two capabilities, both evidence-first and both deliberately conservative:

1. Website-relevance gate - decide whether the site should publish the page at all,
   before any keyword or SERP work. Search volume never green-lights an unrelated
   topic. Verdicts: RELEVANT, CONDITIONALLY_RELEVANT, NOT_RELEVANT, INSUFFICIENT_EVIDENCE.

2. SERP competitor assessment - assess the *observed* competing page set for a query.
   It uses only supplied search results. It never fabricates traffic, backlinks,
   authority, volume, CPC, or performance data, and it never reports a Google score.

The comparison score is an explicitly configurable kit heuristic. It is not a Google
metric, not a ranking factor, and not a probability of ranking.
"""

from __future__ import annotations

from typing import Any, Iterable

# Configurable kit heuristic weights. Not Google weights. Override per project.
DEFAULT_WEIGHTS: dict[str, float] = {
    "intent_fit": 0.25,
    "first_hand_evidence": 0.20,
    "source_quality": 0.15,
    "freshness": 0.15,
    "entity_coverage": 0.15,
    "conversion_fit": 0.10,
}

_REQUIRED_CAPTURE = ("query", "locale", "device", "date", "source")
# A SERP capture ages quickly. Beyond this, treat conclusions as stale, not current.
STALE_AFTER_DAYS = 30
_SITE_FIELDS = ("purpose", "audience", "offerings", "markets", "expertise")


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in str(text)).split() if len(t) > 2}


def assess_relevance(
    site: dict[str, Any],
    topic: str,
    market: str | None = None,
    search_volume: int | None = None,
) -> dict[str, Any]:
    """Decide whether this site should publish this page. Volume is never a reason to."""
    known = [f for f in _SITE_FIELDS if site.get(f)]
    if len(known) < 3:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reasons": ["Site purpose, audience, offerings, markets, or expertise not supplied."],
            "evidence": {"site_fields_supplied": known},
            "note": "Relevance is a kit governance gate, not a Google ranking factor.",
        }

    topic_tokens = _tokens(topic)
    corpus = _tokens(
        " ".join(
            [str(site.get("purpose", "")), str(site.get("audience", ""))]
            + [str(o) for o in site.get("offerings", [])]
            + [str(e) for e in site.get("expertise", [])]
            + [str(t) for t in site.get("existing_topics", [])]
        )
    )
    overlap = topic_tokens & corpus
    reasons: list[str] = []
    evidence = {
        "topic_tokens": sorted(topic_tokens),
        "matched_site_tokens": sorted(overlap),
        "site_fields_supplied": known,
    }

    if not overlap:
        reasons.append(
            "Topic does not intersect the site's stated purpose, offerings, audience or expertise."
        )
        if search_volume:
            reasons.append(
                "Search volume was supplied but is not a reason to publish an unrelated page."
            )
        return {"verdict": "NOT_RELEVANT", "reasons": reasons, "evidence": evidence,
                "note": "Relevance is a kit governance gate, not a Google ranking factor."}

    markets = [str(m).upper() for m in site.get("markets", [])]
    market_ok = (not market) or (not markets) or any(
        str(market).upper() == m or str(market).upper().startswith(m.split("-")[0]) for m in markets
    )
    if not market_ok:
        reasons.append(
            f"Topic market {market} is outside the site's stated market scope {markets}."
        )
        return {"verdict": "CONDITIONALLY_RELEVANT", "reasons": reasons, "evidence": evidence,
                "note": "Relevance is a kit governance gate, not a Google ranking factor."}

    if not site.get("expertise"):
        reasons.append("No first-hand expertise recorded; page needs a credible author or proof.")
        return {"verdict": "CONDITIONALLY_RELEVANT", "reasons": reasons, "evidence": evidence,
                "note": "Relevance is a kit governance gate, not a Google ranking factor."}

    reasons.append("Topic intersects the site's purpose, offerings and expertise, in-market.")
    return {"verdict": "RELEVANT", "reasons": reasons, "evidence": evidence,
            "note": "Relevance is a kit governance gate, not a Google ranking factor."}


def _freshness(last_updated: str | None) -> float:
    if not last_updated:
        return 0.0
    year = str(last_updated)[:4]
    if not year.isdigit():
        return 0.0
    age = 2026 - int(year)
    return 1.0 if age <= 1 else 0.5 if age <= 3 else 0.0


def assess_serp(
    results: Iterable[dict[str, Any]],
    capture: dict[str, Any],
    own_domain: str,
    known_domain_competitors: list[str] | None = None,
    weights: dict[str, float] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Assess the observed competing page set. Uses only supplied results."""
    missing = [k for k in _REQUIRED_CAPTURE if not capture.get(k)]
    if missing:
        raise ValueError(
            "SERP capture must record query, locale, device, date and source; missing: "
            + ", ".join(missing)
        )

    weights = weights or dict(DEFAULT_WEIGHTS)
    domain_competitors = {d.lower() for d in (known_domain_competitors or [])}

    stale = _is_stale(capture.get("date"), as_of)
    intents: set[str] = set()
    inaccessible: list[dict[str, Any]] = []

    seen: set[str] = set()
    competitors: list[dict[str, Any]] = []
    duplicates = 0
    for row in results or []:
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)

        # An unreachable or blocked result is disclosed, never silently dropped and never
        # scored as if it had been read.
        if row.get("inaccessible") or row.get("fetch_error"):
            inaccessible.append({
                "url": url,
                "reason": str(row.get("fetch_error") or "marked inaccessible"),
                "evidence_state": "Not Run",
            })
            continue
        if row.get("intent"):
            intents.add(str(row["intent"]))
        host = url.split("//")[-1].split("/")[0].lower()
        kind = "domain_and_serp" if any(host.endswith(d) for d in domain_competitors) else "serp_only"

        signals = {
            "intent_fit": 1.0 if row.get("intent") else 0.0,
            "first_hand_evidence": 1.0 if row.get("first_hand_evidence") else 0.0,
            "source_quality": 1.0 if row.get("sources_cited") else 0.0,
            "freshness": _freshness(row.get("last_updated")),
            "entity_coverage": min(len(row.get("entities") or []) / 3.0, 1.0),
            "conversion_fit": 1.0 if row.get("conversion_path") else 0.0,
        }
        observed = {k: v for k, v in row.items() if k in
                    ("url", "position", "page_type", "intent", "last_updated", "entities")}
        heuristic = round(sum(signals[k] * weights.get(k, 0.0) for k in signals) * 100, 1)
        competitors.append({
            "url": url,
            "competitor_kind": kind,
            "observed": observed,
            "signals": signals,
            "heuristic_score": heuristic,
            "inference_note": "Signals are inferred from supplied fields, not measured by Google.",
        })

    if not competitors:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "capture": capture,
            "competitors": [],
            "result_count": 0,
            "duplicates_removed": duplicates,
            "inaccessible": inaccessible,
            "stale": stale,
            "mixed_intent": False,
            "score_basis": "kit_heuristic",
            "weights_configurable": True,
            "weights": weights,
            "disclaimer": "Heuristic only. This is not a Google score and not a ranking probability.",
            "missing_evidence": ["No search results were supplied for this query, locale and device."],
        }

    bar = max(c["heuristic_score"] for c in competitors)
    mixed_intent = len(intents) > 1
    return {
        "status": "STALE_EVIDENCE" if stale else "OK",
        "stale": stale,
        "mixed_intent": mixed_intent,
        "intent_note": (
            "The observed results serve more than one intent. Do not average them into a single "
            "target; choose the intent this page will serve and say so."
            if mixed_intent else "Observed results share one dominant intent."
        ),
        "inaccessible": inaccessible,
        "capture": capture,
        "own_domain": own_domain,
        "result_count": len(competitors),
        "duplicates_removed": duplicates,
        "competitors": competitors,
        "bar_to_beat": bar,
        "score_basis": "kit_heuristic",
        "weights_configurable": True,
        "weights": weights,
        "disclaimer": (
            "Heuristic only. This is not a Google score, not a ranking factor, and not a "
            "probability of ranking. Direct observation is separated from inference."
        ),
        "missing_evidence": [],
    }


def _is_stale(captured: str | None, as_of: str | None = None) -> bool:
    """True when the SERP capture is older than STALE_AFTER_DAYS."""
    from datetime import date

    if not captured:
        return True
    try:
        y, m, d = (int(x) for x in str(captured)[:10].split("-"))
        cap = date(y, m, d)
        if as_of:
            ay, am, ad = (int(x) for x in str(as_of)[:10].split("-"))
            today = date(ay, am, ad)
        else:
            today = date.today()
    except (TypeError, ValueError):
        return True
    return (today - cap).days > STALE_AFTER_DAYS


def brief_decision(
    relevance: dict[str, Any],
    serp: dict[str, Any],
    information_gain: list[str],
) -> dict[str, Any]:
    """A brief only proceeds with relevance AND a distinct, stated information gain."""
    verdict = relevance.get("verdict")
    if verdict == "NOT_RELEVANT":
        return {"publish": False, "reason": "Website-relevance gate returned NOT_RELEVANT."}
    if verdict == "INSUFFICIENT_EVIDENCE":
        return {"publish": False, "reason": "Insufficient site evidence to judge relevance."}
    if not information_gain:
        return {
            "publish": False,
            "reason": (
                "No distinct information gain stated. A brief must say what this page adds "
                "beyond the observed results."
            ),
        }
    return {
        "publish": True,
        "reason": "Relevant, with stated information gain.",
        "must_beat": serp.get("bar_to_beat"),
        "information_gain": information_gain,
    }
