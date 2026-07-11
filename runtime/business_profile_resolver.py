"""Canonical business-profile resolution for workflow composition.

This implements the routing model documented in ``docs/plugin-packaging.md`` section 9.
It is a workflow-composition aid, not a factual claim about a business. Explicit user
selection wins. Low-confidence evidence returns the generic profile and a clarification
requirement rather than silently selecting a specialist profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


PROFILES = (
    "generic",
    "ecommerce",
    "local-service",
    "saas",
    "publisher",
    "agency-b2b",
)
ALIASES = {
    "e-commerce": "ecommerce",
    "commerce": "ecommerce",
    "retail": "ecommerce",
    "local": "local-service",
    "local_service": "local-service",
    "local-business": "local-service",
    "agency": "agency-b2b",
    "b2b": "agency-b2b",
}
STRONG_SIGNALS: dict[str, set[str]] = {
    "ecommerce": {
        "product_offer_data", "cart", "checkout", "visible_price", "purchase_action",
        "product_schema", "merchant_feed",
    },
    "local-service": {
        "local_business_schema", "verified_nap", "location_pages", "service_area",
        "store_locator", "google_business_profile",
    },
    "saas": {
        "software_product", "signup_flow", "free_trial", "pricing_plans",
        "software_application_schema",
    },
    "publisher": {
        "high_article_volume", "article_schema", "author_bylines", "subscription_wall",
    },
    "agency-b2b": {
        "service_offerings", "contact_sales", "case_studies", "client_outcomes",
    },
}
SUPPORTING_SIGNALS: dict[str, set[str]] = {
    "ecommerce": {"product_grids", "collections", "shipping_returns"},
    "local-service": {"map_embed", "appointment_action", "local_phone", "hours"},
    "saas": {"docs_site", "integrations", "changelog"},
    "publisher": {"sections", "subscriptions", "editorial_policy", "ad_inventory"},
    "agency-b2b": {"client_logos", "industries_served", "lead_forms", "services_pages"},
}
CONTRADICTORY_SIGNALS: dict[str, set[str]] = {
    "ecommerce": {"no_purchase_path"},
    "local-service": {"no_verifiable_presence"},
    "saas": {"no_software_product"},
    "publisher": {"no_editorial_output"},
    "agency-b2b": {"no_service_offering"},
}
_EXPLICIT_LABELS = (
    "local-service",
    "agency-b2b",
    "e-commerce",
    "ecommerce",
    "publisher",
    "agency",
    "saas",
    "generic",
)


@dataclass(frozen=True)
class BusinessProfileResolution:
    profiles: tuple[str, ...]
    route: str
    confidence: str
    scores: dict[str, int]
    observed_signals: tuple[str, ...]
    user_override: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    action: str
    authority: str = "docs/plugin-packaging.md section 9"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-schema-compatible mapping; tuples are emitted as arrays."""
        return {
            "profiles": list(self.profiles),
            "route": self.route,
            "confidence": self.confidence,
            "scores": dict(self.scores),
            "observed_signals": list(self.observed_signals),
            "user_override": list(self.user_override),
            "missing_evidence": list(self.missing_evidence),
            "action": self.action,
            "authority": self.authority,
        }


def _normalize_profile(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    return ALIASES.get(normalized, normalized)


def _explicit_profiles(value: str) -> tuple[str, ...]:
    normalized = " ".join(value.strip().lower().split())
    if normalized in {"", "unknown", "unconfirmed", "auto"}:
        return ()
    direct = _normalize_profile(normalized)
    if direct in PROFILES:
        return (direct,)

    found: list[tuple[int, str]] = []
    for label in _EXPLICIT_LABELS:
        pattern = rf"(?<![a-z0-9_-]){re.escape(label)}(?![a-z0-9_-])"
        match = re.search(pattern, normalized)
        if match:
            found.append((match.start(), _normalize_profile(label)))
    if found:
        profiles: list[str] = []
        for _, profile in sorted(found):
            if profile not in profiles:
                profiles.append(profile)
        return tuple(profiles)

    parts = re.split(r"\s*(?:\+|,|/|\band\b)\s*", normalized)
    profiles = []
    for item in parts:
        if not item:
            continue
        profile = _normalize_profile(item)
        if profile not in PROFILES:
            raise ValueError(f"unsupported explicit business profile: {item.strip()}")
        if profile not in profiles:
            profiles.append(profile)
    if not profiles:
        raise ValueError(f"unsupported explicit business profile: {value.strip()}")
    return tuple(profiles)


def resolve_business_profile(
    *,
    explicit_business_type: str = "unknown",
    signals: Iterable[str] = (),
) -> BusinessProfileResolution:
    """Resolve workflow profiles with explicit override, evidence, score, and confidence."""
    explicit = _explicit_profiles(explicit_business_type)
    observed = tuple(
        sorted({str(item).strip().lower() for item in signals if str(item).strip()})
    )
    if explicit:
        return BusinessProfileResolution(
            profiles=explicit,
            route="HYBRID" if len(explicit) > 1 else "SINGLE",
            confidence="High",
            scores={profile: 0 for profile in explicit},
            observed_signals=observed,
            user_override=explicit,
            missing_evidence=(),
            action="run_declared_profile",
        )

    scores: dict[str, int] = {}
    signal_set = set(observed)
    for profile in PROFILES:
        if profile == "generic":
            continue
        scores[profile] = (
            3 * len(signal_set & STRONG_SIGNALS[profile])
            + len(signal_set & SUPPORTING_SIGNALS[profile])
            - 2 * len(signal_set & CONTRADICTORY_SIGNALS[profile])
        )

    qualified = sorted(profile for profile, score in scores.items() if score >= 6)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_score = ranked[0][1] if ranked else 0
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if len(qualified) >= 2:
        return BusinessProfileResolution(
            profiles=tuple(qualified),
            route="HYBRID",
            confidence="High",
            scores=scores,
            observed_signals=observed,
            user_override=(),
            missing_evidence=(),
            action="run_declared_hybrid",
        )
    if len(qualified) == 1 and top_score - second_score >= 2:
        return BusinessProfileResolution(
            profiles=(qualified[0],),
            route="SINGLE",
            confidence="High",
            scores=scores,
            observed_signals=observed,
            user_override=(),
            missing_evidence=(),
            action="run_profile",
        )

    return BusinessProfileResolution(
        profiles=("generic",),
        route="UNCONFIRMED",
        confidence="Low",
        scores=scores,
        observed_signals=observed,
        user_override=(),
        missing_evidence=(
            "Business model is not strongly evidenced or the leading score margin is below 2.",
        ),
        action="ask_or_stop_when_profile_changes_execution",
    )
