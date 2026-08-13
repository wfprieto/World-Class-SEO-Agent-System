from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.rehearse_phase_rollback as rollback_module
from scripts.rehearse_phase_rollback import rehearse

ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def test_rollback_cli_bootstraps_before_third_party_dependencies_are_installed() -> None:
    result = subprocess.run(
        [sys.executable, "-S", "scripts/rehearse_phase_rollback.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr


def test_rehearsal_preserves_candidate_and_restores_clean_baseline(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    (root / "baseline.txt").write_text("trusted baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=root, check=True)
    baseline = _git(root, "rev-parse", "HEAD")
    baseline_tree = _git(root, "rev-parse", f"{baseline}^{{tree}}")

    evidence = root / "evaluation/remediation"
    evidence.mkdir(parents=True)
    program = {
        "phases": [
            {
                "id": "P1",
                "status": "IN_PROGRESS",
                "rollback_baseline_commit": baseline,
            }
        ]
    }
    rollback = {
        "baseline_commit": baseline,
        "expected_baseline_tree": baseline_tree,
    }
    (evidence / "owner-controlled-remediation-program.json").write_text(
        json.dumps(program), encoding="utf-8"
    )
    (evidence / "phase1-rollback-evidence.json").write_text(
        json.dumps(rollback), encoding="utf-8"
    )
    (root / "later-phase.txt").write_text("must be reverted\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=root, check=True)
    candidate = _git(root, "rev-parse", "HEAD")

    receipt_path = root / "rollback-receipt.json"
    receipt = rehearse(root, receipt_path)

    assert receipt["candidate_commit"] == candidate
    assert receipt["baseline_commit"] == baseline
    assert receipt["post_revert_tree"] == baseline_tree
    assert _git(root, "rev-parse", "HEAD") == baseline
    assert _git(root, "write-tree") == baseline_tree
    assert subprocess.run(["git", "diff", "--quiet"], cwd=root).returncode == 0
    assert subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode == 0
    assert not (root / "later-phase.txt").exists()


def test_rehearsal_detaches_at_authenticated_source_before_reverting(
    tmp_path: Path, monkeypatch: object
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    (root / "shared.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=root, check=True)
    baseline = _git(root, "rev-parse", "HEAD")
    baseline_tree = _git(root, "rev-parse", f"{baseline}^{{tree}}")
    (root / "shared.txt").write_text("source phase\n", encoding="utf-8")
    subprocess.run(["git", "commit", "--quiet", "-am", "source phase"], cwd=root, check=True)
    candidate = _git(root, "rev-parse", "HEAD")
    subprocess.run(["git", "checkout", "--quiet", "--detach", baseline], cwd=root, check=True)
    evidence = root / "evaluation/remediation"
    evidence.mkdir(parents=True)
    (evidence / "owner-controlled-remediation-program.json").write_text(
        json.dumps(
            {
                "phases": [
                    {"id": "P1", "status": "IN_PROGRESS", "rollback_baseline_commit": baseline}
                ]
            }
        ),
        encoding="utf-8",
    )
    (evidence / "phase1-rollback-evidence.json").write_text(
        json.dumps({"baseline_commit": baseline, "expected_baseline_tree": baseline_tree}),
        encoding="utf-8",
    )
    (root / "shared.txt").write_text("post-merge repair\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "post-merge repair"], cwd=root, check=True)
    monkeypatch.setattr(rollback_module, "rollback_history_head", lambda _root, _baseline: candidate)  # type: ignore[attr-defined]

    receipt = rehearse(root, root / "rollback-receipt.json")

    assert receipt["candidate_commit"] == candidate
    assert _git(root, "rev-parse", "HEAD") == baseline
    assert _git(root, "write-tree") == baseline_tree
