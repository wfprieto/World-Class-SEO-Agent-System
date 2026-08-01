from __future__ import annotations

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
