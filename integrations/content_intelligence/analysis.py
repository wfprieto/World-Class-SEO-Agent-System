"""Pure text-analysis and input-validation primitives.

These helpers measure or validate caller-supplied values only. They do not
fetch evidence, assign semantic truth, or act as a second scoring authority.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlsplit

MAX_TEXT_CHARS = 2_000_000
MAX_RECORDS = 2_000
WORD = re.compile(r"[A-Za-z0-9]+(?:['â€™\-][A-Za-z0-9]+)?")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
FIRST_PERSON = re.compile(r"\b(?:I|we|me|my|mine|us|our|ours)\b", re.IGNORECASE)
URL = re.compile(r"https?://[^\s<>)\]]+")
CITATION = re.compile(r"(?:\[\d+(?:\s*[-,]\s*\d+)*\]|\([A-Z][^()]{0,80},\s*\d{4}[a-z]?\))")
CAPITALIZED = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&.'â€™\-]*|[A-Z]{2,})(?:\s+(?:[A-Z][A-Za-z0-9&.'â€™\-]*|[A-Z]{2,})){0,4}\b"
)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "use", "was", "were", "will", "with",
}
FILLER_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bIn today['â€™]s fast-paced digital landscape,?\s*", re.IGNORECASE), "", "removed_generic_scene_setting"),
    (re.compile(r"\bit is important to note that\s+", re.IGNORECASE), "", "removed_meta_filler"),
    (re.compile(r"\bIt should be noted that\s+", re.IGNORECASE), "", "removed_meta_filler"),
    (re.compile(r"\bIn conclusion,?\s*", re.IGNORECASE), "", "removed_formulaic_transition"),
    (re.compile(r"\bAt the end of the day,?\s*", re.IGNORECASE), "", "removed_cliche"),
)


def validate_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("text must be a string")
    if len(value) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds the {MAX_TEXT_CHARS}-character ceiling")
    if not value.strip():
        raise ValueError("text cannot be empty")
    return value


def bounded_records(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    if len(value) > MAX_RECORDS:
        raise ValueError(f"{name} exceeds the {MAX_RECORDS}-record ceiling")
    if any(not isinstance(item, dict) for item in value):
        raise TypeError(f"every {name} item must be an object")
    return list(value)


def require_unique_ids(rows: list[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = str(row.get("id") or "").strip()
        if not value:
            raise ValueError(f"{label} id is required")
        if value in seen:
            raise ValueError(f"duplicate {label} id: {value}")
        seen.add(value)


def required_string(row: dict[str, Any], key: str, label: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"{label} {key} is required")
    if len(value) > 20_000:
        raise ValueError(f"{label} {key} exceeds the length ceiling")
    return value


def safe_registry_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source url must be an HTTP(S) URL without embedded credentials")


def iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def parse_period(snapshot: dict[str, Any], label: str) -> tuple[date, date]:
    start = iso_date(str(snapshot.get("period_start") or ""), f"{label} period_start")
    end = iso_date(str(snapshot.get("period_end") or ""), f"{label} period_end")
    if start > end:
        raise ValueError(f"{label} period_start must be on or before period_end")
    return start, end


def number_or_none(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric or null")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def words(text: str) -> list[str]:
    return WORD.findall(text)


def sentences(text: str) -> list[str]:
    cleaned = HEADING.sub("", text)
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n{2,}", cleaned) if item.strip()]


def paragraphs(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"\n\s*\n", text)
        if item.strip() and not HEADING.fullmatch(item.strip())
    ]


def normalize_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def diagnostic_check(
    check_id: str, passed: bool, weight: int, evidence: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": check_id,
        "state": "PASS" if passed else "NEEDS_REVIEW",
        "weight": weight,
        "evidence": evidence,
    }


def quality_measurements(text: str) -> dict[str, Any]:
    """Measure editorial structure without interpreting quality or truth."""
    word_rows = words(text)
    sentence_rows = sentences(text)
    paragraph_rows = paragraphs(text)
    headings = [item.strip() for item in HEADING.findall(text)]
    normalized_sentences = [normalize_sentence(item) for item in sentence_rows]
    sentence_counts = Counter(
        item for item in normalized_sentences if len(words(item)) >= 5
    )
    duplicates = sorted(item for item, count in sentence_counts.items() if count > 1)
    sentence_lengths = [len(words(item)) for item in sentence_rows if words(item)]
    paragraph_lengths = [len(words(item)) for item in paragraph_rows if words(item)]
    unique_words = {word.lower() for word in word_rows}
    return {
        "headings": headings,
        "duplicates": duplicates,
        "sentence_lengths": sentence_lengths,
        "paragraph_lengths": paragraph_lengths,
        "first_person": bool(FIRST_PERSON.search(text)),
        "citation_markers": len(CITATION.findall(text)) + len(URL.findall(text)),
        "metrics": {
            "character_count": len(text),
            "word_count": len(word_rows),
            "sentence_count": len(sentence_rows),
            "paragraph_count": len(paragraph_rows),
            "heading_count": len(headings),
            "average_sentence_words": mean(sentence_lengths),
            "average_paragraph_words": mean(paragraph_lengths),
            "long_sentence_count": sum(length > 30 for length in sentence_lengths),
            "duplicate_sentence_count": len(duplicates),
            "lexical_diversity": round(len(unique_words) / len(word_rows), 4) if word_rows else 0.0,
            "citation_marker_count": len(CITATION.findall(text)) + len(URL.findall(text)),
        },
    }


def meaningful_terms(text: str) -> set[str]:
    return {
        word.casefold()
        for word in words(text)
        if len(word) >= 4 and word.casefold() not in STOPWORDS
    }


def protected_tokens(text: str) -> set[str]:
    numbers = re.findall(r"(?<!\w)[+-]?(?:\d[\d,]*)(?:\.\d+)?%?(?!\w)", text)
    urls = URL.findall(text)
    citations = CITATION.findall(text)
    return set(numbers + urls + citations)


def compare_texts(
    left: str, right: str, left_label: str, right_label: str
) -> dict[str, Any]:
    """Return lexical and structural measurements without judging quality."""
    left_sentence_set = {normalize_sentence(item) for item in sentences(left) if item.strip()}
    right_sentence_set = {normalize_sentence(item) for item in sentences(right) if item.strip()}
    left_terms = meaningful_terms(left)
    right_terms = meaningful_terms(right)
    left_headings = [item.strip() for item in HEADING.findall(left)]
    right_headings = [item.strip() for item in HEADING.findall(right)]
    return {
        "left": {
            "label": left_label,
            "word_count": len(words(left)),
            "sentence_count": len(left_sentence_set),
            "headings": left_headings,
            "citation_marker_count": len(CITATION.findall(left)) + len(URL.findall(left)),
        },
        "right": {
            "label": right_label,
            "word_count": len(words(right)),
            "sentence_count": len(right_sentence_set),
            "headings": right_headings,
            "citation_marker_count": len(CITATION.findall(right)) + len(URL.findall(right)),
        },
        "exact_sentence_overlap": sorted(
            item for item in left_sentence_set & right_sentence_set if item
        ),
        "left_unique_terms": sorted(left_terms - right_terms)[:500],
        "right_unique_terms": sorted(right_terms - left_terms)[:500],
        "shared_terms": sorted(left_terms & right_terms)[:500],
        "left_unique_headings": sorted(set(left_headings) - set(right_headings)),
        "right_unique_headings": sorted(set(right_headings) - set(left_headings)),
    }
