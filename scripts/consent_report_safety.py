"""Pure signal projection and redaction for every consent-report branch."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sensitive_data import REDACTED, redact, redact_mapping_keys

SIGNALS = ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization")
_VALID_STATES = {"granted", "denied"}
_VALID_MODES = {"basic", "advanced"}
_REDACT_KEYS = {
    "tc_string", "user_id", "client_id", "gclid", "email", "consent_string",
    "access_token", "refresh_token", "api_key", "authorization", "cookie",
}
_REDACT_KEY_ALIASES = {re.sub(r"[^a-z0-9]", "", key) for key in _REDACT_KEYS}
_REGION = re.compile(r"[A-Z]{2,3}(?:-[A-Z0-9]{1,3})?")


def _project_region(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.upper().strip()
        if _REGION.fullmatch(normalized):
            return normalized
    return "unknown"

def _redact(value: Any, *, key: str = "", _path: tuple[str, ...] = ()) -> Any:
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower().replace("-", "_")
    if re.sub(r"[^a-z0-9]", "", normalized) in _REDACT_KEY_ALIASES or redact(None, key=key) == REDACTED:
        return REDACTED
    if normalized in {"region", "requested_region"}:
        return _project_region(value)
    if normalized in SIGNALS and _path[:-1] != ("consent_state_matrix",):
        return value.lower() if isinstance(value, str) and value.lower() in _VALID_STATES else "[INVALID]"
    if isinstance(value, dict):
        return redact_mapping_keys({
            str(item_key): _redact(item_value, key=str(item_key), _path=(*_path, str(item_key)))
            for item_key, item_value in value.items()
        })
    if isinstance(value, list):
        return [_redact(item, _path=(*_path, "[]")) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, _path=(*_path, "[]")) for item in value]
    return redact(value)


def _region_parts(region: str) -> tuple[str, str | None]:
    normalized = region.upper().strip()
    if "-" in normalized:
        country, subdivision = normalized.split("-", 1)
        return country, subdivision
    return normalized, None


def _project_signals(values: Any) -> tuple[dict[str, str], set[str]]:
    """Retain supported states only; invalid supplied values fail closed without echoing."""
    safe: dict[str, str] = {}
    invalid: set[str] = set()
    if isinstance(values, dict):
        for signal in SIGNALS:
            if signal not in values:
                continue
            value = values[signal]
            if isinstance(value, str) and value.lower() in _VALID_STATES:
                safe[signal] = value.lower()
            else:
                safe[signal] = "denied"
                invalid.add(signal)
    return safe, invalid


def _project_overrides(overrides: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        key: _project_signals(row)[0]
        for key, row in overrides.items()
        if isinstance(key, str) and _REGION.fullmatch(key)
        and isinstance(row, dict)
    }


def _resolve_region_defaults(
    region: str,
    defaults: dict[str, str],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    normalized = _project_region(region)
    country, _ = _region_parts(normalized)
    resolved, invalid = _project_signals(defaults)
    safe_overrides = _project_overrides(overrides)
    applied: list[str] = []
    for candidate in dict.fromkeys((country, normalized)):
        if candidate in safe_overrides:
            row, bad_signals = _project_signals(overrides[candidate])
            invalid.difference_update(row)
            invalid.update(bad_signals)
            resolved.update(row)
            applied.append(candidate)
    return {
        "requested_region": normalized or "unknown",
        "applied_overrides": applied,
        "resolved_defaults": resolved,
        "invalid_default_signals": sorted(invalid),
        "invalid_override_entries": normalized == "unknown" or len(safe_overrides) != len(overrides) or any(
            _project_signals(row)[1] for row in overrides.values()
        ),
        "note": (
            "Country defaults apply before more specific subdivision defaults; "
            "the more specific region wins."
        ),
        **safe_overrides,
    }


def consent_matrix(
    effective_defaults: dict[str, str], invalid_signals: list[str],
    consent_region: bool, region: str, _finding: Callable[..., dict[str, str]],
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    matrix: dict[str, dict[str, str]] = {}
    for signal in SIGNALS:
        raw = str(effective_defaults.get(signal, "missing")).lower()
        if signal in invalid_signals:
            raw = "invalid"
        treated = raw if raw in _VALID_STATES and region != "unknown" else "denied"
        matrix[signal] = {
            "declared_default": raw,
            "treated_as": treated,
            "note": "Missing, unknown, or stale values and unresolved regions are treated as denied, never granted.",
        }
        if raw not in _VALID_STATES:
            findings.append(
                _finding(
                    "high",
                    "state",
                    f"{signal} has a missing, unknown, or invalid default state; it is treated as denied.",
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

    return matrix, findings


def configuration_findings(
    config: dict[str, Any], mode: str, region_resolution: dict[str, Any],
    _finding: Callable[..., dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    if region_resolution["invalid_override_entries"]:
        findings.append(_finding(
            "high", "region", "Invalid regional override entries were excluded or treated as denied.",
            "Use region identifiers and the four supported signals with granted or denied states.",
            "Review the supplied region configuration without retaining identifiers or secret values.",
        ))

    if mode not in _VALID_MODES:
        findings.append(
            _finding(
                "high",
                "mode",
                "Unknown or missing Consent Mode implementation mode.",
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
    return mode, findings


def ordering_findings(
    config: dict[str, Any], _finding: Callable[..., dict[str, str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
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
    return findings


def missing_signal_findings(
    effective_defaults: dict[str, str], _finding: Callable[..., dict[str, str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
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
    return findings


def initialization_findings(
    config: dict[str, Any], _finding: Callable[..., dict[str, str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
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
    return findings


def topology_findings(
    config: dict[str, Any], _finding: Callable[..., dict[str, str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
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
    return findings
