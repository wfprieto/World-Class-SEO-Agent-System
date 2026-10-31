"""Release prerequisites: real metadata and immutable historical regressions."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import validate_release_version as versions
from scripts.generate_release_manifest import build_manifest
from scripts.validate_phase6_readiness import REQUIRED_GATES, validate
from scripts.validate_release_artifacts import validate as validate_artifacts

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = Path(__file__).parent / "fixtures" / "release_readiness_20260801.json"


def _minimal_source(root: Path) -> None:
    (root / "seoctl").mkdir()
    (root / "skills").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "controlled-release-fixture"\nversion = "1.7.1"\n',
        encoding="utf-8",
    )
    (root / "seoctl" / "command-registry.json").write_text(
        json.dumps({"commands": [{"id": "controlled-fixture"}]}), encoding="utf-8"
    )
    (root / "skills" / "skill-catalog.json").write_text(
        json.dumps({"categories": [{"skills": ["controlled-fixture"]}]}), encoding="utf-8"
    )


def test_manifest_names_every_certified_python_version(tmp_path: Path) -> None:
    _minimal_source(tmp_path)
    manifest = build_manifest(tmp_path)
    assert manifest["supported_python"] == ["3.11", "3.12", "3.13"], (
        "release metadata must not omit Python 3.12 from the supported CI matrix"
    )


def test_preparation_uses_module_safe_comparator_before_attestation() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/prepare-publication.yml").read_text())
    assert workflow["jobs"]["attest"]["needs"] == "build"
    source = ast.parse((ROOT / "scripts/publication_prepare.py").read_text())
    commands = [tuple(ast.literal_eval(arg) for arg in node.args[1:])
                for node in ast.walk(source) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "_command"
                and all(isinstance(arg, ast.Constant) for arg in node.args[1:])]
    assert ("-m", "scripts.inventory_comparator") in commands
    assert ("scripts/inventory_comparator.py",) not in commands


def test_historical_release_fixture_cannot_silently_become_approval() -> None:
    record = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    assert record["as_of"] == "2026-08-01"
    assert record["evaluated_target_commit"] == "1dbfc232eb8b8540f2f5a3e5f79fabe54874531d"
    assert record["release_decision"] == "BLOCKED"
    assert set(record["gates"]) == REQUIRED_GATES
    assert record["gates"]["external_reproduction"] == "NOT_RUN"


def test_current_release_state_is_consistent_without_freezing_history() -> None:
    record = json.loads(
        (ROOT / "evaluation/comparative/final-release-readiness.json").read_text(encoding="utf-8")
    )
    assert set(record["gates"]) == REQUIRED_GATES
    assert validate() == []
    errors = validate(require_approved=True)
    if record["release_decision"] == "BLOCKED":
        assert "release publication requires release_decision APPROVED" in errors
    else:
        assert record["release_decision"] == "APPROVED"
    assert any("authenticated detached completion" in error for error in errors), (
        "local readiness labels must never become publication authority"
    )


def test_release_artifact_diagnostics_keep_exact_order(tmp_path: Path) -> None:
    _minimal_source(tmp_path)
    sbom = tmp_path / "sbom.json"
    sbom.write_text(
        json.dumps({"bomFormat": "wrong", "components": [
            {"name": "required", "scope": "required", "version": "NOT_INSTALLED"},
            {"name": "optional", "scope": "optional"},
        ]}), encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"command_count": 0, "skill_count": 2,
                    "files": [{"path": "missing.py", "sha256": "0" * 64},
                              {"path": "pyproject.toml", "sha256": "0" * 64}],
                    "sbom": {"sha256": "0" * 64}}), encoding="utf-8"
    )
    assert validate_artifacts(tmp_path, manifest, sbom) == [
        "SBOM is not CycloneDX 1.5",
        "SBOM component has an unresolved pseudo-version: required",
        "required SBOM component is not lock-resolved: required",
        "optional unresolved SBOM component is not explicit: optional",
        "manifest command inventory is invalid",
        "manifest skill inventory is invalid: expected 1, got 2",
        "manifest file missing: missing.py",
        "manifest hash mismatch: pyproject.toml",
        "manifest SBOM hash mismatch",
    ]


def test_timed_out_tag_lookup_does_not_crash_release_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: object, **kwargs: object) -> bytes:
        raise subprocess.TimeoutExpired("git", 10)

    monkeypatch.setattr(versions.subprocess, "check_output", timeout)
    assert versions._tag_version(tmp_path) is None
