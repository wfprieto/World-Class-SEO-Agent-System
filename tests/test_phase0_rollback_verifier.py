from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_phase0_rollback.py"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_phase0_rollback_verifier_handles_merge_commits(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Rollback Test")
    _git(repo, "config", "user.email", "rollback-test@example.com")

    _write(repo, "README.md", "baseline\n")
    baseline = _commit(repo, "baseline")

    _git(repo, "checkout", "-b", "feature")
    _write(repo, "feature.txt", "feature\n")
    _commit(repo, "feature commit")

    _git(repo, "checkout", "main")
    _write(repo, "main.txt", "main\n")
    _commit(repo, "main commit")
    _git(repo, "merge", "--no-ff", "feature", "-m", "merge feature")
    _write(repo, "after.txt", "after\n")
    _commit(repo, "post-merge commit")

    receipt_path = repo / "phase0-rollback-receipt.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-E",
            "-S",
            str(SCRIPT),
            "--baseline",
            baseline,
            "--receipt",
            str(receipt_path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["result"] == "TREE_MATCH"
    assert receipt["rollback_method"] == "reverse-binary-diff"
    assert receipt["baseline_commit"] == baseline
    assert _git(repo, "rev-parse", "HEAD") == baseline
    assert any(item["mode"] == "merge-recorded" for item in receipt["reverted_commits"])
