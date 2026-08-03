from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from scripts.validate_private_conduct_intake import validate

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 8, 3)


def _copy_surface(tmp_path: Path) -> Path:
    for relative in (
        "schemas/private-conduct-intake.schema.json",
        "governance/private-conduct-intake.json",
        "governance/repository-operations.json",
        "governance/open-issue-remediation.json",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
    ):
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return tmp_path


def _load(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _write(root: Path, relative: str, payload: dict) -> None:
    (root / relative).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_current_blocked_private_intake_is_truthful() -> None:
    assert validate(as_of=AS_OF) == []


def test_repository_only_ready_transition_is_rejected(tmp_path: Path) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake.update(
        {
            "state": "READY",
            "destination": {
                "type": "EMAIL",
                "public_instructions": "mailto:conduct@example.test",
            },
            "owner_authorized_publication": True,
            "repository_controlled": True,
            "distinct_from_security_intake": True,
            "monitoring": {
                "status": "VERIFIED",
                "monitor_role": "Repository maintainer",
                "attested_at": "2026-08-01T12:00:00Z",
                "attestation_ref": (
                    "https://github.com/wfprieto/World-Class-SEO-Agent-System/"
                    "issues/30#issuecomment-123456789"
                ),
            },
            "access_test": {
                "status": "PASS",
                "tested_at": "2026-08-01T12:00:00Z",
                "method": "Self-authored assertion",
            },
            "acknowledgement_target_hours": 72,
        }
    )
    _write(root, "governance/private-conduct-intake.json", intake)

    errors = validate(root, as_of=AS_OF)

    assert any("cannot promote conduct intake to READY" in error for error in errors)
    assert any("example or test destinations" in error for error in errors)
    assert any("cannot establish verified conduct monitoring" in error for error in errors)
    assert any("cannot establish a provider access test" in error for error in errors)


@pytest.mark.parametrize(
    "destination",
    [
        "mailto:conduct@example.com",
        "mailto:conduct@example.test",
        "https://localhost/private-intake",
        "https://tickets.invalid/conduct",
    ],
)
def test_example_and_test_destinations_never_activate(
    tmp_path: Path, destination: str
) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake["destination"] = {"type": "EMAIL", "public_instructions": destination}
    _write(root, "governance/private-conduct-intake.json", intake)
    assert any("example or test destinations" in error for error in validate(root))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("required_disclosures", ["acknowledgement target"], "every required public disclosure"),
        ("prohibited_evidence", ["repository commits"], "reject mutable"),
        ("status", "OWNER_ATTESTED", "provider-verified evidence"),
    ],
)
def test_activation_requirements_cannot_be_weakened(
    tmp_path: Path, field: str, value: object, expected: str
) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake["activation_requirements"][field] = value
    _write(root, "governance/private-conduct-intake.json", intake)
    assert any(expected in error for error in validate(root))


def test_malformed_requirement_collections_fail_without_validator_crash(tmp_path: Path) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake["activation_requirements"]["required_disclosures"] = 7
    intake["prohibited_repository_data"] = {"unexpected": "mapping"}
    _write(root, "governance/private-conduct-intake.json", intake)
    errors = validate(root)
    assert any("every required public disclosure" in error for error in errors)
    assert any("exact prohibited" in error for error in errors)


@pytest.mark.parametrize(
    "disclosure",
    ["acknowledgement target", "monitoring role", "confidentiality limits", "conflict handling"],
)
def test_every_promised_disclosure_is_required_in_public_docs(
    tmp_path: Path, disclosure: str
) -> None:
    root = _copy_surface(tmp_path)
    support = root / "SUPPORT.md"
    support.write_text(
        support.read_text(encoding="utf-8").replace(disclosure, "REMOVED_DISCLOSURE"),
        encoding="utf-8",
    )
    assert any(
        f"future intake disclosure missing from SUPPORT.md: {disclosure}" in error
        for error in validate(root)
    )


def test_linked_governance_cannot_claim_ready(tmp_path: Path) -> None:
    root = _copy_surface(tmp_path)
    operations = _load(root, "governance/repository-operations.json")
    operation = next(row for row in operations["critical_paths"] if row["id"] == "security-intake")
    operation["status"] = "READY"
    operation["blocker"] = None
    operation["closure_evidence"] = {
        "status": "VERIFIED",
        "refs": ["https://github.com/wfprieto/World-Class-SEO-Agent-System/issues/30"],
    }
    _write(root, "governance/repository-operations.json", operations)
    assert any("must remain BLOCKED_OWNER_ACTION" in error for error in validate(root))


def test_unknown_sensitive_field_fails_closed(tmp_path: Path) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake["mailbox_token"] = "must-not-be-stored"
    _write(root, "governance/private-conduct-intake.json", intake)
    assert any("Additional properties" in error for error in validate(root))


def test_prohibited_data_set_cannot_be_weakened(tmp_path: Path) -> None:
    root = _copy_surface(tmp_path)
    intake = _load(root, "governance/private-conduct-intake.json")
    intake["prohibited_repository_data"].remove("reporter identity")
    _write(root, "governance/private-conduct-intake.json", intake)
    assert any("exact prohibited" in error for error in validate(root))
