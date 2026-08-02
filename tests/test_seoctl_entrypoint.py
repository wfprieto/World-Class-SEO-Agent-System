from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from seoctl.entrypoint import main
from seoctl.registry import command_specs

ROOT = Path(__file__).resolve().parents[1]


def test_root_help_exposes_every_registered_command_family(capsys):
    expected_families = {spec.path[0] for spec in command_specs()}

    assert main(["--help"]) == 0

    help_text = capsys.readouterr().out
    for family in expected_families:
        assert family in help_text


def test_root_help_works_from_the_installed_module_entrypoint():
    completed = subprocess.run(
        [sys.executable, "-m", "seoctl", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "audit" in completed.stdout
    assert "intelligence" in completed.stdout
    assert "technical" in completed.stdout


def test_every_registered_family_routes_to_authoritative_family_help(capsys):
    actions_by_family: dict[str, set[str]] = {}
    for spec in command_specs():
        actions_by_family.setdefault(spec.path[0], set()).add(spec.path[1])

    for family, actions in actions_by_family.items():
        with pytest.raises(SystemExit) as exited:
            main([family, "--help"])
        assert exited.value.code == 0
        help_text = capsys.readouterr().out
        for action in actions:
            assert action in help_text


def test_every_registered_command_rejects_invalid_arguments_with_one_json_envelope(
    capsys,
):
    for spec in command_specs():
        assert main([*spec.path, "--definitely-invalid-option"]) == 2
        captured = capsys.readouterr()
        assert captured.err == ""
        payload = json.loads(captured.out)
        assert payload == {
            "command": spec.id,
            "data": None,
            "error": {
                "code": "INVALID_ARGUMENTS",
                "message": "Invalid command arguments.",
                "state": "INPUT_ERROR",
                "type": "ArgumentError",
            },
            "status": "input_error",
            "warnings": [],
        }


def test_every_registered_family_has_stable_missing_and_unknown_command_envelopes(
    capsys,
):
    families = sorted({spec.path[0] for spec in command_specs()})
    for family in families:
        for arguments in ([family], [family, "not-a-registered-command"]):
            assert main(arguments) == 2
            captured = capsys.readouterr()
            assert captured.err == ""
            payload = json.loads(captured.out)
            assert payload["command"] == f"{family}.unknown"
            assert payload["status"] == "input_error"
            assert payload["error"]["code"] == "INVALID_ARGUMENTS"


def test_installed_entrypoint_emits_only_json_for_parser_failure():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "seoctl",
            "content",
            "quality",
            "--definitely-invalid-option",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["command"] == "content.quality"
    assert completed.stdout.count('"command"') == 1
