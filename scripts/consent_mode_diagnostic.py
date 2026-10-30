"""Consent Mode v2 configuration diagnostic using supplied evidence only.

This module performs no network call, emits no consent command, changes no tag, and makes
no legal-compliance determination. Live testing remains separately authorized and scoped.
"""

from __future__ import annotations

from typing import Any

from scripts.consent_report_safety import (
    _VALID_MODES as _VALID_MODES,
)
from scripts.consent_report_safety import (
    SIGNALS as SIGNALS,
)
from scripts.consent_report_safety import (
    _project_overrides,
    _project_signals,
    _redact,
    _region_parts,
    _resolve_region_defaults,
    configuration_findings,
    consent_matrix,
    initialization_findings,
    missing_signal_findings,
    ordering_findings,
    topology_findings,
)

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


def _requires_consent(region: str) -> bool:
    country, _ = _region_parts(region)
    return country in _CONSENT_REQUIRED


def _report_status(config: dict[str, Any], findings: list[dict[str, str]]) -> str:
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
    return status


def _build_report(
    config: dict[str, Any], region: str, consent_region: bool, mode: str,
    defaults: Any, overrides: dict[str, Any], region_resolution: dict[str, Any],
    matrix: dict[str, dict[str, str]], findings: list[dict[str, str]],
) -> dict[str, Any]:
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

    status = _report_status(config, findings)

    observed_config = dict(config)
    observed_config["defaults"] = _project_signals(defaults)[0]
    observed_config["region_overrides"] = _project_overrides(overrides)
    return _redact({
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
            "observed_config": observed_config,
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
            "Recognized credential and identifier fields and labeled secrets are redacted; "
            "arbitrary unlabeled private data is not detected.",
            "No live tag or production change is made.",
        ],
    })


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
    mode = str(config.get("mode", "advanced")).lower().strip()
    defaults = config.get("defaults") or {}
    overrides = config.get("region_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    region_resolution = _resolve_region_defaults(region, defaults, overrides)
    region = str(region_resolution["requested_region"])
    consent_region = region == "unknown" or _requires_consent(region)
    effective_defaults = dict(region_resolution["resolved_defaults"])
    mode, findings = configuration_findings(config, mode, region_resolution, _finding)
    findings.extend(ordering_findings(config, _finding))
    findings.extend(missing_signal_findings(effective_defaults, _finding))

    matrix, state_findings = consent_matrix(
        effective_defaults, region_resolution["invalid_default_signals"], consent_region, region, _finding,
    )
    findings.extend(state_findings)

    findings.extend(initialization_findings(config, _finding))
    findings.extend(topology_findings(config, _finding))
    return _build_report(
        config, region, consent_region, mode, defaults, overrides, region_resolution, matrix, findings,
    )
