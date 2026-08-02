from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


PROTECTED_IMPORT_ROOTS = {"adapters", "integrations", "runtime", "scripts", "seoctl", "tests"}
SHADOW_SUFFIXES = {".py", ".pyc", ".pyi", ".pyo", ".pth"}


def _git(root: Path, *arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Git source-integrity query failed")
    return result.stdout.strip()


def _head_entries(root: Path) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for record in _git(root, "ls-tree", "-r", "-z", "HEAD").split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_type, object_id = metadata.split()
        if object_type == "blob":
            entries[path] = (mode, object_id)
    return entries


def _index_entries(root: Path) -> dict[str, tuple[str, str, str]]:
    entries: dict[str, tuple[str, str, str]] = {}
    for record in _git(root, "ls-files", "--stage", "-z").split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_id, stage = metadata.split()
        entries[path] = (mode, object_id, stage)
    return entries


def _tracked_content_errors(root: Path) -> list[str]:
    expected = _head_entries(root)
    index = _index_entries(root)
    errors: list[str] = []
    expected_index = {
        path: (mode, object_id, "0") for path, (mode, object_id) in expected.items()
    }
    if index != expected_index:
        errors.append("tracked index does not equal the immutable HEAD tree")
    paths = sorted(expected)
    if any("\n" in path or "\r" in path for path in paths):
        return [*errors, "tracked paths containing line breaks cannot be certified"]
    actual_hashes = _git(
        root,
        "hash-object",
        "--stdin-paths",
        input_text="".join(f"{path}\n" for path in paths),
    ).splitlines()
    if len(actual_hashes) != len(paths):
        return [*errors, "tracked worktree content inventory is incomplete"]
    for path, actual_hash in zip(paths, actual_hashes, strict=True):
        mode, expected_hash = expected[path]
        if actual_hash != expected_hash:
            errors.append(f"tracked worktree content differs from HEAD: {path}")
        candidate = root / path
        if os.name != "nt" and mode in {"100644", "100755"}:
            executable = bool(candidate.stat().st_mode & stat.S_IXUSR)
            if executable != (mode == "100755"):
                errors.append(f"tracked worktree mode differs from HEAD: {path}")
    return errors


def _untracked_shadow_errors(root: Path) -> list[str]:
    visible = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    ignored = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    errors: list[str] = []
    for path in sorted(set(filter(None, f"{visible}\0{ignored}".split("\0")))):
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        suffix = Path(normalized).suffix.casefold()
        protected = parts[0] in PROTECTED_IMPORT_ROOTS or len(parts) == 1
        ordinary_cache = "__pycache__" in parts
        if protected and suffix in SHADOW_SUFFIXES and not ordinary_cache:
            errors.append(f"untracked import-shadowing file is forbidden: {normalized}")
    return errors


def validate(expected_sha: str, root: Path = ROOT) -> list[str]:
    """Prove that HEAD, the index, and every tracked worktree file are immutable."""
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        return ["expected event SHA must be exactly 40 hexadecimal characters"]
    try:
        head = _git(root, "rev-parse", "HEAD")
        content_errors = _tracked_content_errors(root)
        shadow_errors = _untracked_shadow_errors(root)
    except RuntimeError as exc:
        return [str(exc)]
    errors: list[str] = []
    if head.casefold() != expected_sha.casefold():
        errors.append("checked-out HEAD does not equal the expected event SHA")
    errors.extend(content_errors)
    errors.extend(shadow_errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    errors = validate(args.expected_sha)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
