from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validate_source_integrity import validate


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(root: Path) -> str:
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Source Integrity Test")
    _git(root, "config", "user.email", "source-integrity@example.invalid")
    (root / "tracked.txt").write_text("canonical\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-m", "canonical")
    return _git(root, "rev-parse", "HEAD")


def test_source_integrity_accepts_exact_clean_commit(tmp_path: Path) -> None:
    expected = _repository(tmp_path / "clean")
    assert validate(expected, tmp_path / "clean") == []


def test_source_integrity_rejects_head_index_and_worktree_drift(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    expected = _repository(worktree)
    (worktree / "tracked.txt").write_text("changed\n", encoding="utf-8")
    assert any("content differs" in error for error in validate(expected, worktree))

    staged = tmp_path / "staged"
    expected = _repository(staged)
    (staged / "tracked.txt").write_text("staged\n", encoding="utf-8")
    _git(staged, "add", "tracked.txt")
    errors = validate(expected, staged)
    assert any("index" in error for error in errors)
    assert any("content differs" in error for error in errors)

    wrong_head = tmp_path / "head"
    expected = _repository(wrong_head)
    (wrong_head / "tracked.txt").write_text("second\n", encoding="utf-8")
    _git(wrong_head, "commit", "-am", "second")
    assert any("HEAD" in error for error in validate(expected, wrong_head))


def test_source_integrity_ignores_assume_unchanged_and_rejects_shadow_modules(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "assume-unchanged"
    expected = _repository(worktree)
    _git(worktree, "update-index", "--assume-unchanged", "tracked.txt")
    (worktree / "tracked.txt").write_text("concealed drift\n", encoding="utf-8")
    assert _git(worktree, "status", "--porcelain") == ""
    assert any("content differs" in error for error in validate(expected, worktree))

    shadowed = tmp_path / "shadowed"
    expected = _repository(shadowed)
    (shadowed / "runtime").mkdir()
    (shadowed / "runtime" / "shadow.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert any("import-shadowing" in error for error in validate(expected, shadowed))


def test_source_integrity_rejects_non_sha_expectation(tmp_path: Path) -> None:
    assert validate("main", tmp_path) == [
        "expected event SHA must be exactly 40 hexadecimal characters"
    ]
