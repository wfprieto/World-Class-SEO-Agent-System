from __future__ import annotations

import socket
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from seoctl.cli import run
from seoctl.doctor import diagnose

ROOT = Path(__file__).resolve().parents[1]


def test_system_doctor_is_deterministic_static_and_read_only(monkeypatch) -> None:
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("system doctor must not perform network I/O")

    monkeypatch.setattr(socket, "getaddrinfo", network_forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", network_forbidden)
    first = diagnose(ROOT, as_of=date(2026, 8, 2), python_version=(3, 13))
    second = diagnose(ROOT, as_of=date(2026, 8, 2), python_version=(3, 13))

    assert first == second
    assert first["status"] == "PASS"
    assert first["scope"] == "STATIC_LOCAL_ONLY"
    assert first["network_performed"] is False
    assert first["provider_authentication_performed"] is False


def test_system_doctor_fails_closed_for_unsupported_python() -> None:
    result = diagnose(ROOT, as_of=date(2026, 8, 2), python_version=(3, 14))
    check = next(item for item in result["checks"] if item["id"] == "python.supported")
    assert result["status"] == "FAIL"
    assert check == {
        "id": "python.supported",
        "status": "FAIL",
        "detail": "unsupported Python 3.14",
    }


def test_system_doctor_reports_every_check_for_missing_repository(tmp_path: Path) -> None:
    result = diagnose(tmp_path, as_of=date(2026, 8, 2), python_version=(3, 13))
    checks = {item["id"]: item for item in result["checks"]}

    assert result["status"] == "FAIL"
    assert set(checks) == {
        "python.supported",
        "assets.required",
        "commands.registry",
        "capabilities.live_certification",
        "agents.specialist_depth",
        "architecture.static",
        "knowledge.provenance",
        "dependencies.lock",
        "operations.contract",
        "remediation.open_issues",
        "conduct.private_intake",
    }
    assert checks["python.supported"]["status"] == "PASS"
    assert all(
        checks[identifier]["status"] == "FAIL"
        for identifier in set(checks) - {"python.supported"}
    )


@pytest.mark.parametrize(
    ("target", "check_id", "failure"),
    [
        ("seoctl.doctor.load_registry", "commands.registry", OSError("registry unreadable")),
        (
            "seoctl.doctor.validate_certification",
            "capabilities.live_certification",
            ValueError("certification corrupt"),
        ),
        (
            "seoctl.doctor.validate_specialist_depth",
            "agents.specialist_depth",
            ValueError("specialist depth corrupt"),
        ),
        (
            "seoctl.doctor.validate_architecture",
            "architecture.static",
            ValueError("architecture corrupt"),
        ),
        (
            "seoctl.doctor.validate_references",
            "knowledge.provenance",
            KeyError("packs"),
        ),
        (
            "seoctl.doctor.validate_dependency_lock",
            "dependencies.lock",
            TypeError("lock malformed"),
        ),
        (
            "seoctl.doctor.validate_operations",
            "operations.contract",
            ValueError("operations malformed"),
        ),
        (
            "seoctl.doctor.validate_open_issues",
            "remediation.open_issues",
            ValueError("remediation malformed"),
        ),
        (
            "seoctl.doctor.validate_conduct_intake",
            "conduct.private_intake",
            ValueError("conduct intake malformed"),
        ),
    ],
)
def test_system_doctor_converts_validator_exceptions_to_structured_failures(
    monkeypatch, target: str, check_id: str, failure: Exception
) -> None:
    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(target, fail)
    result = diagnose(ROOT, as_of=date(2026, 8, 2), python_version=(3, 13))
    checks = {item["id"]: item for item in result["checks"]}

    assert result["status"] == "FAIL"
    assert checks[check_id]["status"] == "FAIL"
    assert type(failure).__name__ in checks[check_id]["detail"]
    assert len(checks) == 11


def test_system_doctor_cli_uses_canonical_json_envelope(monkeypatch) -> None:
    def supported_diagnose(root: Path, *, as_of: date | None = None):
        return diagnose(root, as_of=as_of, python_version=(3, 13))

    monkeypatch.setattr("seoctl.doctor.diagnose", supported_diagnose)
    payload, code = run(["system", "doctor", "--as-of", "2026-08-02"])
    assert code == 0
    assert payload["command"] == "system.doctor"
    assert payload["status"] == "ok"
    assert payload["data"]["status"] == "PASS"
