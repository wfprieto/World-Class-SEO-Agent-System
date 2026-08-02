from __future__ import annotations

import socket
import urllib.request
from datetime import date
from pathlib import Path

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


def test_system_doctor_cli_uses_canonical_json_envelope(monkeypatch) -> None:
    def supported_diagnose(root: Path, *, as_of: date | None = None):
        return diagnose(root, as_of=as_of, python_version=(3, 13))

    monkeypatch.setattr("seoctl.doctor.diagnose", supported_diagnose)
    payload, code = run(["system", "doctor", "--as-of", "2026-08-02"])
    assert code == 0
    assert payload["command"] == "system.doctor"
    assert payload["status"] == "ok"
    assert payload["data"]["status"] == "PASS"
