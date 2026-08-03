from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from seoctl.capability_certification import (
    certification_state,
    credential_preflight,
    implementation_fingerprint,
    load_contract,
    receipt_digest,
    validate_configuration,
    validate_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.fixture
def certification_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    contract = load_contract(ROOT)
    required = {
        "governance/capability-certification.json",
        "schemas/capability-certification.schema.json",
        "schemas/capability-certification-receipt.schema.json",
        "seoctl/command-registry.json",
        "seoctl/command-registry-overlay.json",
        *(source for profile in contract["profiles"] for source in profile["relevant_sources"]),
    }
    for relative in required:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "tested source"], check=True)
    return repo


def _receipt(repo: Path, capability: str = "google.ga4-report") -> dict:
    profile = next(
        item
        for item in load_contract(repo)["profiles"]
        if capability in item["capabilities"]
    )
    tested_commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    receipt_id = capability.replace(".", "-") + "-20260803"
    labels = [
        "prerequisites", "auth_preflight", "fixture_replay", "adverse_cases",
        "live_probe", "redaction", "provider_log", "application_log",
    ]
    evidence: dict[str, dict] = {}
    for index, label in enumerate(labels):
        relative = f"evaluation/provider-evidence/{receipt_id}/{label}.json"
        path = repo / relative
        _write(path, {"label": label, "sequence": index, "sanitized": True})
        evidence[label] = {
            "type": {
                "prerequisites": "source", "auth_preflight": "auth_result",
                "fixture_replay": "fixture_replay", "adverse_cases": "adverse_test",
                "live_probe": "live_observation", "redaction": "redaction_report",
                "provider_log": "provider_log", "application_log": "application_log",
            }[label],
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tested_commit": tested_commit,
        }
    payload = {
        "schema_version": "2.1.0",
        "receipt_id": receipt_id,
        "status": "CANDIDATE",
        "capability": {"kind": "commands", "id": capability},
        "profile": {"id": profile["id"], "version": profile["version"]},
        "provider_identity": {
            "provider_id": profile["provider_id"],
            "account_subject_sha256": "c" * 64,
            "target_subject_sha256": "b" * 64,
        },
        "issuer": {
            "kind": "local_candidate",
            "identity": "repository-test-operator",
            "attestation": None,
        },
        "tested_commit": tested_commit,
        "implementation_fingerprint": implementation_fingerprint(repo, profile),
        "issued_at": "2026-08-03T12:00:00Z",
        "expires_at": "2026-08-30T12:00:00Z",
        "environment": "sandbox",
        "authorization": {
            "live_requested": True,
            "confirmation": "LIVE_CERTIFY",
            "authorized_target_sha256": "b" * 64,
            "cost_approved": bool(profile["live_authorization"]["cost_approval_required"]),
            "write_approved": bool(profile["live_authorization"]["write_approval_required"]),
        },
        "checks": {
            name: {"status": "PASS", "evidence": [evidence[name]]}
            for name in load_contract(repo)["required_checks"]
        },
        "provider_evidence": {
            "request_id_sha256": "e" * 64,
            "provider_log": evidence["provider_log"],
            "application_log": evidence["application_log"],
        },
        "no_secrets": True,
        "digest": "",
    }
    payload["digest"] = receipt_digest(payload)
    return payload


def _validate(repo: Path, payload: dict, name: str = "receipt.json") -> list[str]:
    path = repo / "evaluation/provider-receipts" / name
    _write(path, payload)
    return validate_receipt(repo, path, as_of=date(2026, 8, 3))[1]


def test_profiles_cover_every_live_command_and_preflight_never_returns_values() -> None:
    assert validate_configuration(ROOT) == []
    profile = next(item for item in load_contract(ROOT)["profiles"] if item["id"] == "google-analytics-read-only")
    result = credential_preflight(profile, {"GA4_ACCESS_TOKEN": "do-not-return-this"})
    assert result["status"] == "PASS"
    assert result["network_performed"] is False
    assert result["values_returned"] is False
    assert "do-not-return-this" not in json.dumps(result)


def test_valid_current_receipt_is_accepted(certification_repo: Path) -> None:
    assert _validate(certification_repo, _receipt(certification_repo)) == []
    state = certification_state(certification_repo, as_of=date(2026, 8, 3))
    assert state["errors"] == []
    assert state["current"] == {}
    assert set(state["candidates"]) == {"google.ga4-report"}


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda row: row.update(schema_version="1.0.0"), "receipt invalid"),
        (lambda row: row.update(issued_at="2026-09-03T12:00:00Z"), "future-dated"),
        (lambda row: row.update(expires_at="2026-08-03T11:00:00Z"), "expiry must be after"),
        (lambda row: row.update(expires_at="2026-12-03T12:00:00Z"), "lifetime exceeds"),
        (lambda row: row.update(implementation_fingerprint="0" * 64), "fingerprint"),
        (lambda row: row["profile"].update(id="wrong-profile"), "profile binding"),
        (lambda row: row["issuer"].update(identity="Bearer abcdefghijklmnop"), "credential-shaped"),
    ],
)
def test_receipt_mutations_fail_closed(certification_repo: Path, mutate, expected: str) -> None:
    payload = _receipt(certification_repo)
    mutate(payload)
    payload["digest"] = receipt_digest(payload)
    assert any(expected in error for error in _validate(certification_repo, payload))


def test_digest_tampering_and_missing_evidence_fail_closed(certification_repo: Path) -> None:
    payload = _receipt(certification_repo)
    payload["provider_evidence"]["request_id_sha256"] = "f" * 64
    assert "receipt digest mismatch" in _validate(certification_repo, payload)

    missing = _receipt(certification_repo)
    missing["checks"]["adverse_cases"]["evidence"][0]["path"] = (
        f"evaluation/provider-evidence/{missing['receipt_id']}/missing.json"
    )
    missing["digest"] = receipt_digest(missing)
    assert any("adverse_cases invalid evidence" in error for error in _validate(certification_repo, missing, "missing.json"))


def test_write_and_metered_approvals_are_separate(certification_repo: Path) -> None:
    write = _receipt(certification_repo, "indexnow.submit")
    write["authorization"]["write_approved"] = False
    write["digest"] = receipt_digest(write)
    assert "receipt lacks required write approval" in _validate(certification_repo, write, "write.json")

    metered = _receipt(certification_repo, "system.run")
    metered["authorization"]["cost_approved"] = False
    metered["digest"] = receipt_digest(metered)
    assert "receipt lacks required cost approval" in _validate(certification_repo, metered, "metered.json")


def test_duplicate_current_receipts_fail_repository_state(certification_repo: Path) -> None:
    first = _receipt(certification_repo)
    second = copy.deepcopy(first)
    _validate(certification_repo, first, "one.json")
    _validate(certification_repo, second, "two.json")
    assert "multiple current receipts for capability google.ga4-report" in certification_state(
        certification_repo, as_of=date(2026, 8, 3)
    )["errors"]


def test_relevant_source_change_invalidates_receipt(certification_repo: Path) -> None:
    payload = _receipt(certification_repo)
    path = certification_repo / "evaluation/provider-receipts/receipt.json"
    _write(path, payload)
    source = certification_repo / "integrations/google/ga4.py"
    source.write_text(source.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert any("fingerprint" in error for error in validate_receipt(
        certification_repo, path, as_of=date(2026, 8, 3)
    )[1])


def test_arbitrary_commit_and_wrong_provider_fail_closed(certification_repo: Path) -> None:
    arbitrary = _receipt(certification_repo)
    arbitrary["tested_commit"] = "f" * 40
    for check in arbitrary["checks"].values():
        check["evidence"][0]["tested_commit"] = "f" * 40
    for key in ("provider_log", "application_log"):
        arbitrary["provider_evidence"][key]["tested_commit"] = "f" * 40
    arbitrary["digest"] = receipt_digest(arbitrary)
    assert any("verifiable repository commit" in error for error in _validate(
        certification_repo, arbitrary, "arbitrary.json"
    ))

    wrong = _receipt(certification_repo)
    wrong["provider_identity"]["provider_id"] = "wrong-provider"
    wrong["digest"] = receipt_digest(wrong)
    assert any("provider identity" in error for error in _validate(
        certification_repo, wrong, "wrong-provider.json"
    ))


def test_evidence_reuse_and_forged_external_issuer_cannot_promote(
    certification_repo: Path,
) -> None:
    reused = _receipt(certification_repo)
    reused["checks"]["adverse_cases"]["evidence"] = copy.deepcopy(
        reused["checks"]["fixture_replay"]["evidence"]
    )
    reused["digest"] = receipt_digest(reused)
    assert any("reuses evidence" in error for error in _validate(
        certification_repo, reused, "reused.json"
    ))

    forged = _receipt(certification_repo)
    attestation_path = (
        certification_repo
        / f"evaluation/provider-evidence/{forged['receipt_id']}/attestation.json"
    )
    _write(attestation_path, {"issuer": "self-asserted", "sanitized": True})
    forged["status"] = "PASS"
    forged["issuer"] = {
        "kind": "external_attestation",
        "identity": "self-asserted-external",
        "attestation": {
            "type": "external_attestation",
            "path": attestation_path.relative_to(certification_repo).as_posix(),
            "sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
            "tested_commit": forged["tested_commit"],
        },
    }
    forged["digest"] = receipt_digest(forged)
    assert _validate(certification_repo, forged, "forged.json") == []
    state = certification_state(certification_repo, as_of=date(2026, 8, 3))
    assert state["current"] == {}
    assert set(state["candidates"]) == {"google.ga4-report"}


def test_receipt_removal_demotes_candidate_without_fallback(certification_repo: Path) -> None:
    payload = _receipt(certification_repo)
    path = certification_repo / "evaluation/provider-receipts/candidate.json"
    _write(path, payload)
    assert certification_state(certification_repo, as_of=date(2026, 8, 3))["current"] == {}
    path.unlink()
    state = certification_state(certification_repo, as_of=date(2026, 8, 3))
    assert state["current"] == {}
    assert state["candidates"] == {}


def test_expiry_demotes_and_fails_closed(certification_repo: Path) -> None:
    payload = _receipt(certification_repo)
    payload["expires_at"] = "2026-08-04T00:00:00Z"
    payload["digest"] = receipt_digest(payload)
    path = certification_repo / "evaluation/provider-receipts/expired.json"
    _write(path, payload)
    state = certification_state(certification_repo, as_of=date(2026, 8, 4))
    assert state["current"] == {}
    assert state["candidates"] == {}
    assert any("expired" in error for error in state["errors"])
