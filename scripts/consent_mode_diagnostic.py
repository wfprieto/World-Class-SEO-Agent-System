"""DMA / Consent Mode v2 diagnostic (configuration analysis only).

Analyses a SUPPLIED tag/consent configuration description. It performs no network call,
loads no tag, reads no live CMP, and never emits or modifies a consent command. It cannot
grant, deny, bypass, or manipulate consent, and it never claims legal compliance.

Primary sources (checked 2026-07-11):
- Consent mode setup: https://developers.google.com/tag-platform/security/guides/consent
- Consent mode debugging (Tag Assistant): https://developers.google.com/tag-platform/security/guides/consent-debugging
- Google Ads consent mode reference: https://support.google.com/google-ads/answer/13802165

Established behaviour used by this diagnostic:
- Four signals: ad_storage, analytics_storage, ad_user_data, ad_personalization.
- `default` must be set before any Google tag / GTM container loads and reads consent.
- `update` reflects the user's choice and may fire multiple times; it must follow `default`.
- `wait_for_update` is a one-time per-page window, not a rolling timer.
- Region and subregion defaults: the more specific region wins (for example US-CA over US).
- Advanced mode loads tags before the banner and sends cookieless pings; Basic mode blocks
  tags until consent and relies on modelled measurement.

Legal note: technical configuration is not legal compliance. Any DMA, GDPR, ePrivacy or
consent-validity question requires qualified counsel. This tool separates observed
configuration, provider documentation, technical analysis, and legal uncertainty.
"""

from __future__ import annotations

from typing import Any

SIGNALS = ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization")
CONSENT_REQUIRED_REGIONS = {"EEA", "EU", "UK", "CH"}
_VALID_STATES = {"granted", "denied"}
_REDACT = ("tc_string", "user_id", "client_id", "gclid", "email", "consent_string")

LEGAL_NOTE = (
    "Technical configuration is not legal compliance. Consent validity, DMA and GDPR "
    "obligations require qualified counsel."
)


def _finding(sev: str, area: str, finding: str, correction: str, validation: str,
             privacy: str = "none") -> dict[str, str]:
    return {
        "severity": sev,
        "area": area,
        "finding": finding,
        "technical_correction": correction,
        "validation_method": validation,
        "privacy_impact": privacy,
        "evidence": "observed configuration (supplied)",
    }


def _redact(config: dict[str, Any]) -> dict[str, Any]:
    """Never echo consent strings, identifiers, or user data back into the report."""
    return {k: v for k, v in config.items() if k not in _REDACT}


def diagnose(config: dict[str, Any]) -> dict[str, Any]:
    """Diagnose a supplied consent configuration. Never grants or bypasses consent."""
    if not isinstance(config, dict):
        raise TypeError("config must be a dict describing the observed configuration")

    # Live testing against a real CMP, tag, or ad account is a separate authorisation.
    if config.get("live_test_requested") and not config.get("live_test_authorized"):
        return {
            "status": "BLOCKED",
            "reason": (
                "Live consent testing was requested without explicit written authorisation. "
                "Live tests can create advertising or analytics writes and touch production "
                "tags. Supply an authorisation and scope, or run against fixtures."
            ),
            "findings": [],
            "legal_review_required": True,
            "legal_note": LEGAL_NOTE + " Consult qualified counsel.",
            "evidence_inventory": {"live_verification": "Blocked (unauthorised)"},
        }

    region = str(config.get("region", "")).upper()
    consent_region = any(region.startswith(r) for r in CONSENT_REQUIRED_REGIONS)
    mode = str(config.get("mode", "advanced")).lower()
    defaults: dict[str, str] = dict(config.get("defaults") or {})
    findings: list[dict[str, str]] = []

    # --- CMP presence -------------------------------------------------------
    if not config.get("cmp"):
        findings.append(_finding(
            "critical", "cmp",
            "No CMP is recorded. Consent state cannot be collected or proven.",
            "Install a CMP that sets the consent default before tags load. Do not grant consent "
            "on the user's behalf.",
            "Tag Assistant: confirm a default command precedes tag initialisation.",
            privacy="high",
        ))

    # --- Default present and ordered before tags ---------------------------
    if not config.get("default_set"):
        findings.append(_finding(
            "critical", "ordering",
            "No consent default command is set. Tags may read consent before a default exists.",
            "Set a consent default for all four signals before any Google tag or GTM container loads.",
            "Tag Assistant: check the default command appears before the first tag read.",
        ))
    elif not config.get("default_before_tags"):
        findings.append(_finding(
            "critical", "ordering",
            "A tag reads consent before the default is set (default is not before tags).",
            "Move the consent default above the Google tag / GTM snippet so it runs first.",
            "Tag Assistant: 'a tag read consent state before a default was set' must not appear.",
        ))

    # --- Update present and ordered after default --------------------------
    if not config.get("update_present"):
        findings.append(_finding(
            "high", "ordering",
            "No consent update command is recorded; the user's choice is never propagated.",
            "Call the consent update command when the user makes or changes a choice.",
            "Tag Assistant: observe an update after interacting with the banner.",
        ))
    elif not config.get("update_after_default"):
        findings.append(_finding(
            "critical", "ordering",
            "Consent update fires before the default command. Command order is invalid.",
            "Emit the default first, then the update on user choice. Update may fire repeatedly.",
            "Tag Assistant: confirm default precedes update within the same page load.",
        ))

    # --- Four signals present ----------------------------------------------
    for signal in SIGNALS:
        if signal not in defaults:
            sev = "critical" if signal in ("ad_user_data", "ad_personalization") else "high"
            findings.append(_finding(
                sev, "signals",
                f"{signal} is not set in the consent default.",
                f"Set {signal} explicitly in the default command. Consent Mode v2 requires all four "
                "signals: ad_storage, analytics_storage, ad_user_data, ad_personalization.",
                "Tag Assistant: all four signals appear in the default command.",
            ))

    # --- Region-appropriate defaults ---------------------------------------
    for signal, state in defaults.items():
        state_l = str(state).lower()
        if state_l not in _VALID_STATES:
            findings.append(_finding(
                "high", "state",
                f"{signal} default is '{state}', which is not a valid consent state; treated as denied.",
                "Use only 'granted' or 'denied' in the default. An unknown or stale value must never "
                "be treated as granted.",
                "Tag Assistant: inspect the resolved consent state.",
            ))
        elif consent_region and state_l == "granted":
            findings.append(_finding(
                "critical", "state",
                f"{signal} defaults to granted in a consent-required region ({region}).",
                "Default all four signals to denied in consent-required regions and only change state "
                "from the user's own choice via the update command.",
                "Tag Assistant: default shows denied before interaction.",
                privacy="high",
            ))

    # --- Consent state matrix ----------------------------------------------
    matrix: dict[str, dict[str, str]] = {}
    for signal in SIGNALS:
        raw = str(defaults.get(signal, "missing")).lower()
        treated = raw if raw in _VALID_STATES else "denied"
        matrix[signal] = {
            "declared_default": raw,
            "treated_as": treated,
            "note": "Missing, unknown or stale states are treated as denied, never as granted.",
        }

    # --- wait_for_update ----------------------------------------------------
    wait = config.get("wait_for_update_ms")
    if wait is None:
        findings.append(_finding(
            "medium", "timing",
            "wait_for_update is not set; tags may send data before the user's choice arrives.",
            "Set wait_for_update in the default command. It is a one-time window per page load, "
            "not a rolling timer.",
            "Tag Assistant: confirm tags hold until update or the window elapses.",
        ))

    # --- Duplicates, SPA, environments -------------------------------------
    if config.get("duplicate_tags"):
        findings.append(_finding(
            "high", "initialisation",
            "Duplicate tag initialisation detected; consent state may race between containers.",
            "Remove the duplicate Google tag / GTM container. One initialisation per page.",
            "Tag Assistant: only one container initialises.",
        ))
    if config.get("spa"):
        findings.append(_finding(
            "medium", "spa",
            "SPA detected: consent state must persist and update on client-side route changes.",
            "Re-assert consent state on route change and ensure the update is captured on the page "
            "where the choice occurs, before any transition.",
            "Tag Assistant: navigate a client-side route and confirm consent persists.",
        ))
    if config.get("server_side_tagging"):
        findings.append(_finding(
            "high", "server-side",
            "Server-side tagging is present: consent state must be forwarded to the server "
            "container, or the server may send data the user never consented to.",
            "Propagate the consent state to the server container and enforce it there. A denied "
            "client-side state must not become a granted server-side send.",
            "Inspect the server container: confirm consent is read and enforced per request.",
            privacy="high",
        ))
    if config.get("cross_domain"):
        findings.append(_finding(
            "high", "cross-domain",
            "Cross-domain journey detected: consent state does not automatically carry across "
            "domains and may silently reset.",
            "Propagate consent across the linked domains, or re-collect it on the second domain. "
            "Never assume consent granted on domain A applies to domain B.",
            "Traverse the cross-domain path and confirm the resolved consent state on arrival.",
            privacy="high",
        ))
    if config.get("production_config_differs"):
        findings.append(_finding(
            "high", "environment",
            "Preview and Production consent configuration differ; Preview evidence is not proof of "
            "Production behaviour.",
            "Reconcile the Preview and Production containers and re-verify in Production.",
            "Compare published container versions across environments.",
        ))

    # --- Region resolution --------------------------------------------------
    overrides = config.get("region_overrides") or {}
    region_resolution: dict[str, Any] = dict(overrides)
    region_resolution["note"] = (
        "Where a region and a subregion both set a default, the more specific region wins "
        "(for example US-CA overrides US)."
    )

    # --- Mode behaviour -----------------------------------------------------
    if mode == "basic":
        mode_behavior = (
            "Basic: tags are blocked until the user consents. No pings are sent before consent, "
            "so non-consented behaviour relies on modeled measurement."
        )
    else:
        mode_behavior = (
            "Advanced: tags load before the banner and send cookieless pings without identifiers "
            "until consent is granted."
        )

    severities = [f["severity"] for f in findings]
    if not config.get("cmp") and "critical" in severities:
        status = "BLOCKED"
    elif "critical" in severities:
        status = "FAIL"
    elif findings:
        status = "PARTIAL"
    else:
        status = "PASS"
    if not consent_region and not findings:
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
            "All four signals set in the default command.",
            "Default precedes any tag read; update follows default and reflects the user's choice.",
            "Consent-required regions default to denied.",
            "No duplicate initialisation; SPA route changes preserve consent state.",
        ],
        "modeled_measurement_note": (
            "Modelled conversions and behavioural modelling are estimates produced by Google, not "
            "observed user data. Do not report modelled figures as measured."
        ),
        "rollback": (
            "Revert to the previously published container version and re-verify with Tag Assistant. "
            "Do not change live tags or consent settings without explicit authorisation."
        ),
        "legal_review_required": True,
        "legal_note": LEGAL_NOTE + " This diagnostic does not constitute legal advice and does not "
                                   "assert compliance with the DMA or any other law; consult qualified counsel.",
        "guardrails": [
            "Consent is never granted automatically by this tool.",
            "The CMP is never bypassed or manipulated.",
            "No consent strings, identifiers, or user data are recorded in this report.",
            "No live tag or production change is made.",
        ],
    }
