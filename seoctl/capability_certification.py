"""Offline authority for capability-certification profiles and sanitized receipts.

This module never performs provider calls.  Credential preflight reports names and
presence only; live execution belongs to a separately authorized operator workflow.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

from sensitive_data import redact

CONTRACT = Path("governance/capability-certification.json")
CONTRACT_SCHEMA = Path("schemas/capability-certification.schema.json")
RECEIPT_SCHEMA = Path("schemas/capability-certification-receipt.schema.json")
RECEIPT_ROOT = Path("evaluation/provider-receipts")
def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload
def _safe_file(root: Path, reference: object) -> tuple[Path | None, str | None]:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        return None, "must be a non-empty repository-relative POSIX path"
    relative = PurePosixPath(reference)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None, "must be a normalized repository-relative path"
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None, "must resolve to an existing file inside the repository"
    if candidate.is_symlink() or not resolved.is_file():
        return None, "must be a regular non-symlink file"
    return resolved, None
def load_contract(root: Path) -> dict[str, Any]:
    root = root.resolve()
    contract = _object(root / CONTRACT)
    schema = _object(root / CONTRACT_SCHEMA)
    jsonschema.Draft202012Validator(schema).validate(contract)
    return contract
def _network_commands(root: Path) -> set[str]:
    base = _object(root / "seoctl/command-registry.json")
    overlay = _object(root / "seoctl/command-registry-overlay.json")
    commands = [*base.get("commands", []), *overlay.get("commands", [])]
    return {
        str(row["id"])
        for row in commands
        if row.get("network") in {"provider_optional", "live_optional", "live_required"}
    }
def validate_configuration(root: Path) -> list[str]:
    root = root.resolve()
    try:
        contract = load_contract(root)
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        return [f"capability certification contract invalid: {exc}"]
    errors: list[str] = []
    profile_ids: set[str] = set()
    covered: dict[str, str] = {}
    for profile in contract["profiles"]:
        profile_id = str(profile["id"])
        if profile_id in profile_ids:
            errors.append(f"duplicate certification profile: {profile_id}")
        profile_ids.add(profile_id)
        authorization = profile["live_authorization"]
        if profile["side_effect"] == "write" and not authorization["write_approval_required"]:
            errors.append(f"{profile_id}: write profile must require write approval")
        for capability in profile["capabilities"]:
            if capability in covered:
                errors.append(
                    f"capability {capability} appears in both {covered[capability]} and {profile_id}"
                )
            covered[capability] = profile_id
        for reference in profile["relevant_sources"]:
            _, problem = _safe_file(root, reference)
            if problem:
                errors.append(f"{profile_id}: invalid relevant source {reference!r}: {problem}")
    expected = _network_commands(root)
    actual = set(covered)
    if actual != expected:
        errors.append(
            "live capability profile coverage mismatch; "
            f"missing={sorted(expected - actual)}; extra={sorted(actual - expected)}"
        )
    return errors


def profiles_by_capability(root: Path) -> dict[str, dict[str, Any]]:
    errors = validate_configuration(root)
    if errors:
        raise ValueError("; ".join(errors))
    contract = load_contract(root)
    return {
        str(capability): profile
        for profile in contract["profiles"]
        for capability in profile["capabilities"]
    }


def implementation_fingerprint(root: Path, profile: Mapping[str, Any]) -> str:
    references = sorted(str(item) for item in profile["relevant_sources"])
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    unstaged = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "--", *references], check=False
    ).returncode
    staged = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--quiet", "--", *references],
        check=False,
    ).returncode
    if not unstaged and not staged:
        return implementation_fingerprint_at_commit(root, profile, head)
    digest = hashlib.sha256()
    for reference in references:
        path, problem = _safe_file(root.resolve(), reference)
        if problem or path is None:
            raise ValueError(f"invalid relevant source {reference!r}: {problem}")
        digest.update(reference.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git(root: Path, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
    )
    if process.returncode:
        raise ValueError("tested commit is not a verifiable repository commit")
    return process.stdout


def implementation_fingerprint_at_commit(
    root: Path, profile: Mapping[str, Any], commit: str
) -> str:
    resolved = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    if resolved != commit:
        raise ValueError("tested commit must be an exact full commit SHA")
    digest = hashlib.sha256()
    for reference in sorted(str(item) for item in profile["relevant_sources"]):
        content = _git(root, "show", f"{commit}:{reference}")
        digest.update(reference.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def credential_preflight(
    profile: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Report credential-name readiness without returning or contacting credentials."""
    env = os.environ if environment is None else environment
    choices = [list(group) for group in profile["credential_env_sets"]]
    satisfied = not choices or any(all(bool(env.get(name)) for name in group) for group in choices)
    return {
        "status": "PASS" if satisfied else "BLOCKED",
        "provider": profile["provider"],
        "accepted_credential_sets": choices,
        "credential_set_present": satisfied,
        "network_performed": False,
        "values_returned": False,
    }


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in receipt.items() if key != "digest"}
    encoded = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _secret_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _secret_strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _secret_strings(nested)]
    if isinstance(value, str) and redact(value) != value:
        return [value]
    return []


def _load_receipt(
    root: Path, path: Path
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]] | None, list[str]]:
    try:
        relative = path.resolve().relative_to(root)
    except (OSError, ValueError):
        return None, None, ["receipt resolves outside the repository"]
    if path.is_symlink() or relative.parent != RECEIPT_ROOT or path.suffix != ".json":
        return None, None, [
            f"receipt must be a direct non-symlink JSON file under {RECEIPT_ROOT.as_posix()}"
        ]
    try:
        receipt = _object(path)
        schema = _object(root / RECEIPT_SCHEMA)
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).validate(receipt)
        return receipt, profiles_by_capability(root), []
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        return None, None, [f"receipt invalid: {exc}"]


def _source_binding_errors(
    root: Path, receipt: Mapping[str, Any], profile: Mapping[str, Any]
) -> list[str]:
    try:
        tested_fingerprint = implementation_fingerprint_at_commit(
            root, profile, str(receipt["tested_commit"])
        )
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    if receipt["implementation_fingerprint"] != tested_fingerprint:
        errors.append("receipt fingerprint does not match the exact tested commit")
    if receipt["implementation_fingerprint"] != implementation_fingerprint(root, profile):
        errors.append("receipt implementation fingerprint is stale or mismatched")
    return errors


def _profile_errors(
    root: Path,
    receipt: Mapping[str, Any],
    profiles: Mapping[str, dict[str, Any]],
) -> list[str]:
    capability = str(receipt["capability"]["id"])
    profile = profiles.get(capability)
    if profile is None:
        return [f"receipt references unknown live capability {capability}"]
    errors: list[str] = []
    if receipt["profile"] != {"id": profile["id"], "version": profile["version"]}:
        errors.append("receipt profile binding does not match the capability profile")
    if receipt["provider_identity"]["provider_id"] != profile["provider_id"]:
        errors.append("receipt provider identity does not match the capability profile")
    if (
        receipt["provider_identity"]["target_subject_sha256"]
        != receipt["authorization"]["authorized_target_sha256"]
    ):
        errors.append("provider target identity does not match the authorized target")
    errors.extend(_source_binding_errors(root, receipt, profile))
    authorization = receipt["authorization"]
    live_contract = profile["live_authorization"]
    if live_contract["cost_approval_required"] and not authorization["cost_approved"]:
        errors.append("receipt lacks required cost approval")
    if live_contract["write_approval_required"] and not authorization["write_approved"]:
        errors.append("receipt lacks required write approval")
    if profile["side_effect"] == "read_only" and authorization["write_approved"]:
        errors.append("read-only receipt must not claim write approval")
    return errors


def _time_errors(root: Path, receipt: Mapping[str, Any], as_of: date | None) -> list[str]:
    try:
        issued = _instant(receipt["issued_at"])
        expires = _instant(receipt["expires_at"])
        cutoff = datetime.combine(as_of or date.today(), time.max, tzinfo=UTC)
        max_age = load_contract(root)["max_receipt_age_days"]
    except (TypeError, ValueError) as exc:
        return [f"receipt timestamp invalid: {exc}"]
    errors: list[str] = []
    if issued > cutoff:
        errors.append("receipt is future-dated")
    if expires <= issued:
        errors.append("receipt expiry must be after issuance")
    if (expires - issued).total_seconds() > max_age * 86400:
        errors.append(f"receipt lifetime exceeds {max_age} days")
    if expires <= cutoff:
        errors.append("receipt is expired")
    return errors


def _evidence_reference_errors(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    evidence_rows = [
        (check_name, evidence)
        for check_name, check in receipt["checks"].items()
        for evidence in check["evidence"]
    ]
    evidence_rows.extend(
        (field, receipt["provider_evidence"][field])
        for field in ("provider_log", "application_log")
    )
    if receipt["issuer"]["attestation"] is not None:
        evidence_rows.append(("issuer_attestation", receipt["issuer"]["attestation"]))
    errors: list[str] = []
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    required_prefix = f"evaluation/provider-evidence/{receipt['receipt_id']}/"
    for label, evidence in evidence_rows:
        reference = str(evidence["path"])
        if not reference.startswith(required_prefix):
            errors.append(f"{label} evidence is outside the receipt-specific directory")
        path, problem = _safe_file(root, reference)
        if problem:
            errors.append(f"{label} invalid evidence reference {reference!r}: {problem}")
            continue
        if reference in seen_paths or evidence["sha256"] in seen_hashes:
            errors.append(f"{label} reuses evidence path or content")
        seen_paths.add(reference)
        seen_hashes.add(str(evidence["sha256"]))
        if evidence["tested_commit"] != receipt["tested_commit"]:
            errors.append(f"{label} evidence tested_commit does not match receipt")
        assert path is not None
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
            errors.append(f"{label} evidence hash mismatch")
    return errors


def _issuer_errors(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    issuer = receipt["issuer"]
    if issuer["kind"] == "local_candidate":
        if receipt["status"] != "CANDIDATE" or issuer["attestation"] is not None:
            return ["local issuer must produce an unattested CANDIDATE receipt"]
        return []
    if receipt["status"] != "PASS" or issuer["attestation"] is None:
        return ["external issuer requires PASS status and an attestation reference"]
    if issuer["attestation"]["type"] != "external_attestation":
        return ["external issuer requires typed external-attestation evidence"]
    return []


def _trusted_for_promotion(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    """No issuer is trusted until an authenticated external verifier is implemented."""
    return False


def validate_receipt(
    root: Path, path: Path, *, as_of: date | None = None
) -> tuple[dict[str, Any] | None, list[str]]:
    root = root.resolve()
    receipt, profiles, errors = _load_receipt(root, path)
    if receipt is None or profiles is None:
        return None, errors
    errors.extend(_profile_errors(root, receipt, profiles))
    errors.extend(_time_errors(root, receipt, as_of))
    errors.extend(_evidence_reference_errors(root, receipt))
    errors.extend(_issuer_errors(root, receipt))
    if _secret_strings(receipt):
        errors.append("receipt contains credential-shaped material")
    if receipt["digest"] != receipt_digest(receipt):
        errors.append("receipt digest mismatch")
    return receipt, errors


def certification_state(root: Path, *, as_of: date | None = None) -> dict[str, Any]:
    root = root.resolve()
    configuration_errors = validate_configuration(root)
    if configuration_errors:
        return {"errors": configuration_errors, "current": {}, "candidates": {}, "receipt_count": 0}
    current: dict[str, str] = {}
    candidates: dict[str, str] = {}
    errors: list[str] = []
    paths = sorted((root / RECEIPT_ROOT).glob("*.json")) if (root / RECEIPT_ROOT).is_dir() else []
    for path in paths:
        receipt, receipt_errors = validate_receipt(root, path, as_of=as_of)
        if receipt_errors:
            errors.extend(f"{path.name}: {error}" for error in receipt_errors)
            continue
        assert receipt is not None
        capability = str(receipt["capability"]["id"])
        if capability in current or capability in candidates:
            errors.append(f"multiple current receipts for capability {capability}")
        elif _trusted_for_promotion(load_contract(root), receipt):
            current[capability] = path.relative_to(root).as_posix()
        else:
            candidates[capability] = path.relative_to(root).as_posix()
    return {
        "errors": errors,
        "current": current,
        "candidates": candidates,
        "receipt_count": len(paths),
    }


def validate(root: Path, *, as_of: date | None = None) -> list[str]:
    return list(certification_state(root, as_of=as_of)["errors"])
