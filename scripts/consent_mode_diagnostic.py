"""Consent Mode v2 configuration diagnostic using supplied evidence only.

This module performs no network call, emits no consent command, changes no tag, and makes
no legal-compliance determination. Live testing remains separately authorized and scoped.
"""

from __future__ import annotations

from typing import Any

SIGNALS = ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization")
_VALID_STATES = {"granted", "denied"}
_VALID_MODES = {"basic", "advanced"}
_REDACT_KEYS = {
    "tc_string", "user_id", "client_id", "gclid", "email", "consent_string",
    "access_token", "refresh_token", "api_key", "authorization", "cookie",
}
# ISO country codes plus compatibility aliases used by supplied audit fixtures.
_CONSENT_REQUIRED = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO",
    "PL", "PT", "RO", "SE", "SI", "SK", "GB", "UK", "CH", "EEA", "EU",
}

LEGAL_NOTE = (
    "Technical configuration is not legal compliance. Consent validity, DMA, GDPR, "
    "ePrivacy, and regional obligations require qualified counsel."
)


def _finding(
    severity: str,
    area: str,
    finding: str,
    correction: str,
    validation: str,
    *,
    privacy: str = "none",
    classification: str = "observed_defect",
) -> dict[str, str]:
    return {
        "severity": severity,
        "area": area,
        "finding": finding,
        "technical_correction": correction,
        "validation_method": validation,
        "privacy_impact": privacy,
        "evidence": "observed configuration (supplied)",
        "classification": classification,
    }


def _redact(value: Any, *, key: str = "") -> Any:
    normalized = key.lower().replace("-", "_")
    if normalized in _REDACT_KEYS or any(
        marker in normalized for marker in ("password", "secret", "private_key")
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _region_parts(region: str) -> tuple[str, str | None]:
    normalized = region.upper().strip()
    if "-" in normalized:
        country, subdivision = normalized.split("-", 1)
        return country, subdivision
    return normalized, None


def _requires_consent(region: str) -> bool:
    country, _ = _region_parts(region)
    return country in _CONSENT_REQUIRED


def _resolve_region_defaults(
    region: str,
    defaults: dict[str, str],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    normalized = region.upper().strip()
    country, _ = _region_parts(normalized)
    resolved = dict(defaults)
    applied: list[str] = []
    for candidate in (country, normalized):
        row = overrides.get(candidate)
        if isinstance(row, dict):
            resolved.update({str(key): str(value) for key, value in row.items()})
            applied.append(candidate)
    return {
        "requested_region": normalized or "unknown",
        "applied_overrides": applied,
        "resolved_defaults": resolved,
        "note": (
            "Country defaults apply before more specific subdivision defaults; "
            "the more specific region wins."
        ),
        **{str(key): value for key, value in overrides.items()},
    }


def diagnose(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise TypeError("config must be a dict describing the observed configuration")

    if config.get("live_test_requested") and not config.get("live_test_authorized"):
        return {
            "status": "BLOCKED",
            "reason": (
                "Live consent testing was requested without explicit written authorization. "
                "Use fixtures or supply the approved environment, operations, and write boundaries."
            ),
            "findings": [],
            "legal_review_required": True,
            "legal_note": LEGAL_NOTE,
            "evidence_inventory": {"live_verification": "Blocked (unauthorized)"},
        }

    region = str(config.get("region", "")).upper().strip()
    consent_region = _requires_consent(region)
    mode = str(config.get("mode", "advanced")).lower().strip()
    defaults = {
        str(key): str(value)
        for key, value in dict(config.get("defaults") or {}).items()
    }
    overrides = config.get("region_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    region_resolution = _resolve_region_defaults(region, defaults, overrides)
    effective_defaults = dict(region_resolution["resolved_defaults"])
    findings: list[dict[str, str]] = []

    if mode not in _VALID_MODES:
        findings.append(
            _finding(
                "high",
                "mode",
                f"Unknown Consent Mode implementation mode: {mode or 'missing'}.",
                "Declare either basic or advanced mode and verify the actual tag-loading behavior.",
                "Tag Assistant and network evidence confirm whether tags are blocked or send cookieless pings.",
            )
        )
        mode = "unknown"

    if not config.get("cmp"):
        findings.append(
            _finding(
                "critical",
                "cmp",
                "No CMP is recorded; consent collection and proof are unavailable.",
                "Use an approved CMP or document the authorized consent collection mechanism. Never act on the user's behalf.",
                "Tag Assistant confirms a default before tag initialization and an update after user choice.",
                privacy="high",
            )
        )

    if not config.get("default_set"):
        findings.append(
            _finding(
                "critical",
                "ordering",
                "No consent default command is recorded.",
                "Set all four consent signals before any Google tag or GTM container reads consent.",
                "Tag Assistant shows the default before the first consent read.",
            )
        )
    elif not config.get("default_before_tags"):
        findings.append(
            _finding(
                "critical",
                "ordering",
                "A tag reads consent before the default is set.",
                "Move the default before the Google tag or GTM snippet.",
                "The Tag Assistant ordering warning no longer appears.",
            )
        )

    choice_observed = bool(config.get("user_choice_observed", config.get("update_present")))
    if choice_observed and not config.get("update_present"):
        findings.append(
            _finding(
                "high",
                "ordering",
                "A user choice was observed but no consent update was recorded.",
                "Send the consent update when the user makes or changes a choice.",
                "Tag Assistant observes the update on the page where the choice occurs.",
            )
        )
    elif config.get("update_present") and not config.get("update_after_default"):
        findings.append(
            _finding(
                "critical",
                "ordering",
                "Consent update fires before the default command.",
                "Emit the default first and update only from the user's choice.",
                "Tag Assistant confirms default precedes every update.",
            )
        )

    for signal in SIGNALS:
        if signal not in effective_defaults:
            severity = "critical" if signal in {"ad_user_data", "ad_personalization"} else "high"
            findings.append(
                _finding(
                    severity,
                    "signals",
                    f"{signal} is not set in the resolved consent default.",
                    f"Set {signal} explicitly; all four Consent Mode v2 signals are required.",
                    "Tag Assistant shows all four signals in the resolved default.",
                )
            )

    matrix: dict[str, dict[str, str]] = {}
    for signal in SIGNALS:
        raw = str(effective_defaults.get(signal, "missing")).lower()
        treated = raw if raw in _VALID_STATES else "denied"
        matrix[signal] = {
            "declared_default": raw,
            "treated_as": treated,
            "note": "Missing, unknown, or stale values are treated as denied, never granted.",
        }
        if raw not in _VALID_STATES:
            findings.append(
                _finding(
                    "high",
                    "state",
                    f"{signal} has invalid default state {raw!r}; it is treated as denied.",
                    "Use only granted or denied and derive changes from the user's choice.",
                    "Tag Assistant shows a valid resolved state.",
                )
            )
        elif consent_region and raw == "granted":
            findings.append(
                _finding(
                    "critical",
                    "state",
                    f"{signal} defaults to granted for consent-required region {region}.",
                    "Default all four signals to denied and change state only from the user's own choice.",
                    "Before interaction, Tag Assistant shows denied.",
                    privacy="high",
                )
            )

    wait = config.get("wait_for_update_ms")
    if config.get("async_cmp") and wait is None:
        findings.append(
            _finding(
                "medium",
                "timing",
                "The asynchronous CMP has no wait_for_update window.",
                "Set a bounded one-time wait window only when needed for asynchronous CMP loading.",
                "Tag Assistant confirms the update arrives before the window expires.",
            )
        )
    elif wait is not None and (not isinstance(wait, int) or wait < 0):
        findings.append(
            _finding(
                "medium",
                "timing",
                "wait_for_update is not a non-negative integer.",
                "Use a bounded millisecond integer and verify its effect on the page load.",
                "Tag Assistant confirms the intended one-time wait behavior.",
            )
        )

    if config.get("duplicate_tags"):
        findings.append(
            _finding(
                "high",
                "initialisation",
                "Duplicate tag initialization is observed and may race consent state.",
                "Remove the duplicate initialization and preserve one controlled container path.",
                "Tag Assistant shows one initialization path.",
            )
        )
    if config.get("spa"):
        defect = config.get("spa_state_lost") is True
        findings.append(
            _finding(
                "high" if defect else "medium",
                "spa",
                (
                    "SPA navigation loses or misapplies consent state."
                    if defect
                    else "SPA consent persistence has not been verified across route changes."
                ),
                "Persist and re-apply the resolved state without granting consent or replaying stale choices.",
                "Navigate client-side routes and confirm the resolved state remains correct.",
                classification="observed_defect" if defect else "verification_required",
            )
        )
    if config.get("server_side_tagging"):
        defect = config.get("server_consent_not_enforced") is True
        findings.append(
            _finding(
                "critical" if defect else "high",
                "server-side",
                (
                    "Server-side tagging sends data without enforcing the client consent state."
                    if defect
                    else "Server-side consent forwarding and enforcement require verification."
                ),
                "Forward and enforce consent per request; denied client state must not become a granted server send.",
                "Inspect the server container and request evidence for each consent state.",
                privacy="high",
                classification="observed_defect" if defect else "verification_required",
            )
        )
    if config.get("cross_domain"):
        defect = config.get("cross_domain_state_lost") is True
        findings.append(
            _finding(
                "high",
                "cross-domain",
                (
                    "Consent state resets incorrectly across domains."
                    if defect
                    else "Cross-domain consent behavior requires scoped verification."
                ),
                "Use an approved propagation or re-collection design; never assume one domain's state applies to another domain.",
                "Traverse the approved cross-domain path and inspect the resolved state on arrival.",
                privacy="high",
                classification="observed_defect" if defect else "verification_required",
            )
        )
    if config.get("production_config_differs"):
        findings.append(
            _finding(
                "high",
                "environment",
                "Preview and Production consent configurations differ.",
                "Reconcile the published container and verify the production version.",
                "Compare published container versions and production Tag Assistant evidence.",
            )
        )

    mode_behavior = {
        "basic": (
            "Basic: tags are blocked until consent; non-consented measurement is modeled "
            "rather than directly observed."
        ),
        "advanced": (
            "Advanced: tags may load before interaction and send cookieless pings until "
            "consent is granted."
        ),
        "unknown": "Unknown mode: no behavior claim is made until observed.",
    }[mode]

    severities = [
        item["severity"]
        for item in findings
        if item["classification"] == "observed_defect"
    ]
    if not config.get("cmp"):
        status = "BLOCKED"
    elif "critical" in severities:
        status = "FAIL"
    elif findings:
        status = "PARTIAL"
    else:
        status = "PASS"

    return {
        "status": status,
        "implementation_topology": {
            "region": region or "unknown",
            "consent_required_region": consent_region,
            "cmp": bool(config.get("cmp")),
            "mode": mode,
            "environment": config.get("environment", "unknown"),
            "server_side_tagging": bool(config.get("server_side_tagging")),
        },
        "evidence_inventory": {
            "source": "supplied configuration description",
            "observed_config": _redact(config),
            "live_verification": "Not Run (no live tag, CMP, or production access)",
        },
        "consent_state_matrix": matrix,
        "region_resolution": region_resolution,
        "mode_behavior": mode_behavior,
        "findings": findings,
        "owner": "Analytics/Tagging owner with Privacy owner",
        "acceptance_criteria": [
            "All four signals are set in the resolved default.",
            "Default precedes any tag read and updates reflect only the user's choice.",
            "Consent-required regions resolve to denied before interaction.",
            "SPA, server-side, cross-domain, and environment behavior is verified where applicable.",
        ],
        "modeled_measurement_note": (
            "Modeled conversions and behavioral modeling are estimates, not observed user data."
        ),
        "rollback": (
            "Revert to the previously published container version and re-verify. "
            "Do not change live tags without authorization."
        ),
        "legal_review_required": True,
        "legal_note": LEGAL_NOTE,
        "guardrails": [
            "Consent is never set automatically by this tool.",
            "The CMP is never bypassed or manipulated.",
            "No consent strings, identifiers, or user data are retained in this report.",
            "No live tag or production change is made.",
        ],
    }
