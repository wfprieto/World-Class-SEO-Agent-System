"""Validate imported assessment shape/coherence, not provider authenticity."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit


def text_rows(value: Any, *, allow_empty: bool = False) -> bool:
    return (isinstance(value, list) and (bool(value) or allow_empty)
            and all(isinstance(item, str) and bool(item.strip()) for item in value))


def _number(value: Any, maximum: float) -> bool:
    return type(value) in {int, float} and 0 <= value <= maximum and math.isfinite(value)


def freshness(last_updated: str | None, as_of: str | None = None) -> float:
    if not last_updated:
        return 0.0
    try:
        updated = date.fromisoformat(str(last_updated)[:10])
        current = date.fromisoformat(str(as_of)[:10]) if as_of else date.today()
    except (TypeError, ValueError):
        return 0.0
    age_days = (current - updated).days
    return 1.0 if age_days <= 365 else 0.5 if age_days <= 1095 else 0.0


def serp_signals(row: dict[str, Any], target_intent: str | None = None,
                 as_of: str | None = None) -> dict[str, float]:
    """Canonical producer derivation, also used to challenge imported summaries."""
    row_intent = str(row.get('intent', '')).strip().lower()
    return {
        'intent_fit': 1.0 if row_intent and (not target_intent or row_intent == target_intent.lower()) else 0.0,
        'first_hand_evidence': 1.0 if row.get('first_hand_evidence') else 0.0,
        'source_quality': 1.0 if row.get('sources_cited') else 0.0,
        'freshness': freshness(row.get('last_updated'), as_of),
        'entity_coverage': min(len(row.get('entities') or []) / 3.0, 1.0),
        'conversion_fit': 1.0 if row.get('conversion_path') else 0.0,
    }


def relevance_evidence_valid(value: dict[str, Any], site_fields: tuple[str, ...]) -> bool:
    evidence = value.get('evidence')
    if not isinstance(evidence, dict):
        return False
    rows = [evidence.get(key) for key in ('topic_tokens', 'matched_site_tokens', 'site_fields_supplied')]
    if not all(text_rows(row) for row in rows):
        return False
    topic: set[str] = set(evidence['topic_tokens'])
    matched: set[str] = set(evidence['matched_site_tokens'])
    fields: set[str] = set(evidence['site_fields_supplied'])
    conditions = value.get('conditions')
    if not text_rows(conditions, allow_empty=True):
        return False
    expected_conditions = bool(conditions) if value.get('verdict') == 'CONDITIONALLY_RELEVANT' else not conditions
    return all((text_rows(value.get('reasons')), len(fields) >= 3,
                fields <= set(site_fields), matched <= topic, expected_conditions))


def _capture_current(capture: Any, required: tuple[str, ...], stale_days: int) -> bool:
    if not isinstance(capture, dict):
        return False
    if not all(isinstance(capture.get(key), str) and capture[key].strip() for key in required):
        return False
    try:
        captured = datetime.fromisoformat(capture['date']).date()
    except ValueError:
        return False
    return 0 <= (date.today() - captured).days <= stale_days


def _competitor_valid(row: Any, signal_names: tuple[str, ...]) -> bool:
    if not isinstance(row, dict):
        return False
    observed, signals, url = row.get('observed'), row.get('signals'), row.get('url')
    if not isinstance(observed, dict) or not isinstance(signals, dict) or not isinstance(url, str):
        return False
    if observed.get('inaccessible') or observed.get('fetch_error'):
        return False
    if not all(type(observed.get(key)) is bool for key in
               ('first_hand_evidence', 'sources_cited', 'conversion_path')):
        return False
    try:
        parsed = urlsplit(url)
        public_form = parsed.scheme in {'http', 'https'} and bool(parsed.hostname)
    except ValueError:
        return False
    observed_url = observed.get('url')
    same_url = isinstance(observed_url, str) and observed_url.strip() == url
    return all((public_form, same_url,
                row.get('competitor_kind') in {'serp_only', 'domain_and_serp'},
                set(signals) == set(signal_names),
                all(_number(signals.get(key), 1) for key in signal_names),
                _number(row.get('heuristic_score'), 100)))


def _scores_agree(value: dict[str, Any], rows: list[dict[str, Any]], names: tuple[str, ...]) -> bool:
    weights = value.get('weights')
    if not isinstance(weights, dict) or set(weights) != set(names):
        return False
    if not all(_number(weights[key], 1) for key in names):
        return False
    if not math.isclose(sum(weights.values()), 1):
        return False
    expected = [round(sum(row['signals'][key] * weights[key] for key in names) * 100, 1)
                for row in rows]
    return (all(row['heuristic_score'] == score for row, score in zip(rows, expected, strict=True))
            and _number(value.get('bar_to_beat'), 100) and value['bar_to_beat'] == max(expected))


def _observations_agree(value: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    urls = {row['url'].rstrip('/') for row in rows}
    intents = {str(row['observed'].get('intent', '')).strip().lower() for row in rows}
    intents.discard('')
    return len(urls) == len(rows) and value.get('mixed_intent') is (len(intents) > 1)


def _assessment_date(value: dict[str, Any]) -> str | None:
    capture, assessed = value.get('capture'), value.get('assessed_as_of')
    if not isinstance(capture, dict) or not isinstance(assessed, str):
        return None
    try:
        recorded = date.fromisoformat(assessed)
        captured = datetime.fromisoformat(capture['date']).date()
    except (KeyError, TypeError, ValueError):
        return None
    return assessed if captured <= recorded <= date.today() else None


def _derived_signals_agree(value: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    assessed, intent = _assessment_date(value), value.get('target_intent')
    if assessed is None or not (intent is None or isinstance(intent, str)):
        return False
    try:
        return all(row['signals'] == serp_signals(row['observed'], intent, assessed) for row in rows)
    except (TypeError, ValueError, OverflowError):
        return False


def _availability_agrees(value: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    inaccessible = value.get('inaccessible')
    if not isinstance(inaccessible, list):
        return False
    readable = {row['url'].rstrip('/') for row in rows}
    for row in inaccessible:
        if not isinstance(row, dict) or not isinstance(row.get('url'), str):
            return False
        if row['url'].strip().rstrip('/') in readable:
            return False
    return True


def serp_evidence_valid(value: dict[str, Any], required_capture: tuple[str, ...],
                        stale_days: int, signal_names: tuple[str, ...]) -> bool:
    rows = value.get('competitors')
    if not isinstance(rows, list) or not rows:
        return False
    if not all(_competitor_valid(row, signal_names) for row in rows):
        return False
    return all((_capture_current(value.get('capture'), required_capture, stale_days),
                value.get('stale') is False, type(value.get('mixed_intent')) is bool,
                type(value.get('result_count')) is int, value.get('result_count') == len(rows),
                value.get('missing_evidence') == [], value.get('score_basis') == 'kit_heuristic',
                _scores_agree(value, rows, signal_names), _observations_agree(value, rows),
                _derived_signals_agree(value, rows), _availability_agrees(value, rows)))
