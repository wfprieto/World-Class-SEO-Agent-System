from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import rehearse_autonomous_seo_rollback as rollback


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str, filename: str, content: str) -> str:
    (root / filename).write_text(content, encoding="utf-8")
    _git(root, "add", filename)
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, str, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "WCSEO test")
    _git(root, "config", "user.email", "wcseo-test@example.invalid")
    authority = _commit(root, "authority", "authority.txt", "authority\n")
    integration_base = _commit(root, "main advancement", "main.txt", "preserve me\n")
    _git(root, "checkout", "-b", "candidate")
    program_path = root / "evaluation" / "remediation"
    program_path.mkdir(parents=True)
    program = {
        "program_id": "autonomous-seo-expansion",
        "baseline": {"commit": authority},
        "phases": [{"id": "P0", "status": "IN_PROGRESS"}],
    }
    (program_path / "autonomous-seo-expansion-program.json").write_text(
        json.dumps(program), encoding="utf-8"
    )
    (root / "p0.txt").write_text("candidate\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "P0 candidate")
    candidate = _git(root, "rev-parse", "HEAD")
    return root, authority, integration_base, candidate


def test_rollback_preserves_post_authority_main_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, authority, integration_base, candidate = _repo(tmp_path)
    monkeypatch.setattr(rollback, "ROOT", root)
    monkeypatch.setattr(
        rollback,
        "PROGRAM",
        root / "evaluation" / "remediation" / "autonomous-seo-expansion-program.json",
    )
    monkeypatch.setattr(
        rollback,
        "P0_CLOSURE",
        root / "evaluation" / "remediation" / "autonomous-seo-expansion-p0-closure.json",
    )
    monkeypatch.setenv("WCSEO_INTEGRATION_BASE_REF", "main")

    receipt = rollback.rehearse(root / "rollback-receipt.json")

    assert receipt["candidate_commit"] == candidate
    assert receipt["authority_baseline_commit"] == authority
    assert receipt["baseline_commit"] == integration_base
    assert receipt["result"] == "TREE_MATCH"
    assert _git(root, "rev-parse", "HEAD") == integration_base
    assert (root / "main.txt").read_text(encoding="utf-8") == "preserve me\n"
    assert not (root / "p0.txt").exists()


def test_rollback_rejects_candidate_behind_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, authority, _integration_base, candidate = _repo(tmp_path)
    _git(root, "checkout", "main")
    _commit(root, "new main work", "new-main.txt", "new\n")
    _git(root, "checkout", "candidate")
    monkeypatch.setattr(rollback, "ROOT", root)
    monkeypatch.setenv("WCSEO_INTEGRATION_BASE_REF", "main")
    program = {"baseline": {"commit": authority}}

    with pytest.raises(RuntimeError, match="behind the integration target"):
        rollback._recovery_baseline(program, candidate)
