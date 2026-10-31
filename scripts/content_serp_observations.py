"""Observed SERP evidence, filtering, and explicit heuristic scoring."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from scripts.content_brief_validation import serp_signals

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


def _is_stale(captured: str | None, as_of: str | None = None) -> bool:
    if not captured:
        return True
    try:
        captured_date = date.fromisoformat(str(captured)[:10])
        current = date.fromisoformat(str(as_of)[:10]) if as_of else date.today()
    except (TypeError, ValueError):
        return True
    return (current - captured_date).days > STALE_AFTER_DAYS


def _competitor_result(
    row: dict[str, Any],
    url: str,
    host: str,
    domain_competitors: set[str],
    active_weights: dict[str, float],
    target_intent: str | None,
    assessed_as_of: str,
) -> dict[str, Any]:
    kind = (
        "domain_and_serp"
        if any(_domain_matches(host, domain) for domain in domain_competitors)
        else "serp_only"
    )
    signals = serp_signals(row, target_intent, assessed_as_of)
    observed = {
        key: value
        for key, value in row.items()
        if key in ("url", "position", "page_type", "intent", "last_updated", "entities")
    }
    observed.update(
        {
            key: bool(row.get(key))
            for key in ("first_hand_evidence", "sources_cited", "conversion_path")
        }
    )
    heuristic = round(
        sum(signals[key] * active_weights[key] for key in signals) * 100,
        1,
    )
    return {
        "url": url,
        "competitor_kind": kind,
        "observed": observed,
        "signals": signals,
        "heuristic_score": heuristic,
        "inference_note": "Signals are inferred from supplied fields, not measured by Google.",
    }


def _collect_serp_observations(
    results: Iterable[dict[str, Any]],
    own_host: str,
    domain_competitors: set[str],
    active_weights: dict[str, float],
    target_intent: str | None,
    assessed_as_of: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], int, int]:
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
            inaccessible.append(
                {
                    "url": url,
                    "reason": str(row.get("fetch_error") or "marked inaccessible"),
                    "evidence_state": "Not Run",
                }
            )
            continue
        row_intent = str(row.get("intent", "")).strip().lower()
        if row_intent:
            intents.add(row_intent)
        competitors.append(
            _competitor_result(
                row, url, host, domain_competitors, active_weights, target_intent, assessed_as_of
            )
        )
    return competitors, inaccessible, intents, duplicates, own_results_excluded


def _insufficient_serp_result(
    capture: dict[str, Any],
    assessed_as_of: str,
    active_weights: dict[str, float],
    stale: bool,
    inaccessible: list[dict[str, Any]],
    duplicates: int,
    own_results_excluded: int,
) -> dict[str, Any]:
    reason = (
        "Search results were supplied but none were readable competitor pages."
        if inaccessible or own_results_excluded
        else "No search results were supplied for this query, locale and device."
    )
    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "capture": capture,
        "assessed_as_of": assessed_as_of,
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
    assessed_as_of = str(as_of or date.today().isoformat())[:10]
    stale = _is_stale(capture.get("date"), assessed_as_of)
    competitors, inaccessible, intents, duplicates, own_results_excluded = (
        _collect_serp_observations(
            results, own_host, domain_competitors, active_weights, target_intent, assessed_as_of
        )
    )

    if not competitors:
        return _insufficient_serp_result(
            capture,
            assessed_as_of,
            active_weights,
            stale,
            inaccessible,
            duplicates,
            own_results_excluded,
        )

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
        "assessed_as_of": assessed_as_of,
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
