from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.validate_source_integrity import validate


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(root: Path, tracked: dict[str, str] | None = None) -> str:
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Source Integrity Test")
    _git(root, "config", "user.email", "source-integrity@example.invalid")
    (root / "tracked.txt").write_text("canonical\n", encoding="utf-8")
    for relative, content in (tracked or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(root, "add", ".")
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
        "expected candidate SHA must be exactly 40 hexadecimal characters"
    ]


def test_source_integrity_supports_candidate_and_restored_baseline_modes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "modes"
    source = Path(__file__).parents[1] / "scripts" / "validate_source_integrity.py"
    expected = _repository(
        root,
        {"scripts/validate_source_integrity.py": source.read_text(encoding="utf-8")},
    )
    assert validate(expected, root, proof_mode="candidate") == []
    assert validate(expected, root, proof_mode="restored-baseline") == []
    assert validate(expected, root, proof_mode="unknown") == [
        "proof mode must be candidate or restored-baseline"
    ]
    cli = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "validate_source_integrity.py"),
            "--expected-sha",
            expected,
            "--proof-mode",
            "restored-baseline",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 0
    assert json.loads(cli.stdout)["proof_mode"] == "restored-baseline"

    (root / "tracked.txt").write_text("drift\n", encoding="utf-8")
    errors = validate(expected, root, proof_mode="restored-baseline")
    assert any("content differs" in error for error in errors)
    assert (root / "tracked.txt").read_text(encoding="utf-8") == "drift\n"


def test_source_integrity_rejects_cross_platform_native_module_shadows(
    tmp_path: Path,
) -> None:
    for index, relative in enumerate(
        (
            "runtime/native.pyd",
            "runtime/native.cp313-win_amd64.pyd",
            "runtime/native.so",
            "runtime/native.cpython-313-x86_64-linux-gnu.so",
            "native.pyd",
            "native.so",
        )
    ):
        root = tmp_path / f"native-{index}"
        expected = _repository(root)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"not a real extension")
        assert any(relative in error for error in validate(expected, root))


def test_source_integrity_rejects_top_level_packages_and_launchers(
    tmp_path: Path,
) -> None:
    cases = (
        "subprocess.py",
        "shadow_package/__init__.py",
        "shadow_native/__init__.abi3.so",
        "runtime/rogue/__init__.py",
        "pytest.exe",
        "scripts/git.cmd",
    )
    for index, relative in enumerate(cases):
        root = tmp_path / f"root-shadow-{index}"
        expected = _repository(root)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("shadow\n", encoding="utf-8")
        assert any(relative in error for error in validate(expected, root))


def test_source_integrity_bootstraps_before_repository_module_imports(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parents[1] / "scripts" / "validate_source_integrity.py"
    root = tmp_path / "bootstrap"
    expected = _repository(
        root,
        {"scripts/validate_source_integrity.py": source.read_text(encoding="utf-8")},
    )
    (root / "scripts" / "json.py").write_text(
        "raise RuntimeError('repository json shadow imported')\n", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "validate_source_integrity.py"),
            "--expected-sha",
            expected,
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any("scripts/json.py" in error for error in payload["errors"])
    assert "repository json shadow imported" not in result.stderr

    (root / "scripts" / "json.py").write_text("SHADOW = True\n", encoding="utf-8")
    (root / "scripts" / "sitecustomize.py").write_text(
        "import json\n", encoding="utf-8"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "scripts")
    preloaded = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "validate_source_integrity.py"),
            "--expected-sha",
            expected,
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert preloaded.returncode == 1
    preloaded_payload = json.loads(preloaded.stdout)
    assert (
        "untrusted preloaded bootstrap module origin: json"
        in preloaded_payload["errors"]
    )


def test_source_integrity_allows_non_importable_artifacts_and_ordinary_cache(
    tmp_path: Path,
) -> None:
    root = tmp_path / "negative-controls"
    expected = _repository(root)
    artifacts = {
        "outputs/report.so": b"report data",
        "docs/example.py": b"documentation example\n",
        "runtime/__pycache__/cache.cpython-313.pyc": b"ordinary cache",
        "notes/shadow_package/readme.txt": b"not importable",
    }
    for relative, content in artifacts.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    assert validate(expected, root) == []
