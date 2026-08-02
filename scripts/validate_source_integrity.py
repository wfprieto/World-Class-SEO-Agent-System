from __future__ import annotations

# The script directory is first on sys.path when this file is executed directly.
# Establish a base-interpreter-only import path before importing shadowable stdlib
# modules, then restore the caller's path after the trusted imports are loaded.
import sys as _sys


def _normalized_bootstrap_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").casefold()


def _is_trusted_bootstrap_entry(value: str, prefixes: tuple[str, ...]) -> bool:
    normalized = _normalized_bootstrap_path(value)
    if not normalized or "/../" in f"/{normalized}/":
        return False
    if "/site-packages" in normalized or "/dist-packages" in normalized:
        return False
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in prefixes
    )


_ORIGINAL_SYS_PATH = list(_sys.path)
_BOOTSTRAP_PREFIXES = tuple(
    dict.fromkeys(
        _normalized_bootstrap_path(value)
        for value in (_sys.base_prefix, _sys.base_exec_prefix)
        if value
    )
)
_TRUSTED_SYS_PATH = [
    value
    for value in _ORIGINAL_SYS_PATH
    if _is_trusted_bootstrap_entry(value, _BOOTSTRAP_PREFIXES)
]
_BOOTSTRAP_MODULE_NAMES = (
    "argparse",
    "importlib.machinery",
    "json",
    "os",
    "pathlib",
    "re",
    "shutil",
    "stat",
    "subprocess",
)
_PRELOADED_BOOTSTRAP_ERRORS: list[str] = []
for _bootstrap_name in _BOOTSTRAP_MODULE_NAMES:
    _preloaded = _sys.modules.get(_bootstrap_name)
    if _preloaded is None:
        continue
    _preloaded_origin = getattr(getattr(_preloaded, "__spec__", None), "origin", None)
    if _preloaded_origin in {"built-in", "frozen"} or (
        _preloaded_origin is not None
        and _is_trusted_bootstrap_entry(str(_preloaded_origin), _BOOTSTRAP_PREFIXES)
    ):
        continue
    _PRELOADED_BOOTSTRAP_ERRORS.append(
        f"untrusted preloaded bootstrap module origin: {_bootstrap_name}"
    )
    for _loaded_name in tuple(_sys.modules):
        if _loaded_name == _bootstrap_name or _loaded_name.startswith(
            f"{_bootstrap_name}."
        ):
            _sys.modules.pop(_loaded_name, None)
_sys.path[:] = _TRUSTED_SYS_PATH
try:
    import argparse
    import importlib.machinery as _machinery
    import json
    import os
    import pathlib as _pathlib
    import re
    import shutil
    import stat
    import subprocess
finally:
    _sys.path[:] = _ORIGINAL_SYS_PATH

Path = _pathlib.Path

ROOT = Path(__file__).resolve().parents[1]


PROOF_MODES = {"candidate", "restored-baseline"}
PROTECTED_IMPORT_ROOTS = {
    "adapters",
    "integrations",
    "runtime",
    "scripts",
    "seoctl",
    "tests",
}
PYTHON_SHADOW_SUFFIXES = tuple(
    sorted(
        {
            ".py",
            ".pyc",
            ".pyi",
            ".pyo",
            ".pth",
            ".pyd",
            ".so",
            *(suffix.casefold() for suffix in _machinery.EXTENSION_SUFFIXES),
        },
        key=len,
        reverse=True,
    )
)
WINDOWS_LAUNCHER_SUFFIXES = {".bat", ".cmd", ".com", ".exe", ".ps1"}


def _module_origin_is_trusted(module: object) -> bool:
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    if origin in {"built-in", "frozen"}:
        return True
    return origin is not None and _is_trusted_bootstrap_entry(
        str(origin), _BOOTSTRAP_PREFIXES
    )


_BOOTSTRAP_ERRORS = list(_PRELOADED_BOOTSTRAP_ERRORS)
if not _TRUSTED_SYS_PATH:
    _BOOTSTRAP_ERRORS.append("trusted base-interpreter bootstrap path is unavailable")
for _name, _module in (
    ("argparse", argparse),
    ("importlib.machinery", _machinery),
    ("json", json),
    ("os", os),
    ("pathlib", _pathlib),
    ("re", re),
    ("shutil", shutil),
    ("stat", stat),
    ("subprocess", subprocess),
):
    if not _module_origin_is_trusted(_module):
        _BOOTSTRAP_ERRORS.append(f"untrusted bootstrap module origin: {_name}")


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _git_executable(root: Path) -> str:
    resolved = shutil.which("git")
    if not resolved:
        raise RuntimeError("trusted Git executable is unavailable")
    git_path = Path(resolved).resolve()
    if _is_within(git_path, root.resolve()):
        raise RuntimeError("Git executable must resolve outside the repository")
    return str(git_path)


def _git(root: Path, *arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        [_git_executable(root), *arguments],
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


def _has_python_shadow_suffix(path: str) -> bool:
    normalized = path.casefold()
    return normalized.endswith(PYTHON_SHADOW_SUFFIXES)


def _is_executable_launcher(candidate: Path, suffix: str) -> bool:
    if suffix in WINDOWS_LAUNCHER_SUFFIXES:
        return True
    try:
        return os.name != "nt" and candidate.is_file() and bool(
            candidate.stat().st_mode & stat.S_IXUSR
        )
    except OSError:
        return True


def _is_top_level_package_artifact(parts: list[str], normalized: str) -> bool:
    if len(parts) != 2:
        return False
    filename = parts[1].casefold()
    return filename == "__init__.py" or (
        filename.startswith("__init__.") and _has_python_shadow_suffix(normalized)
    )


def _untracked_shadow_errors(root: Path) -> list[str]:
    visible = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    ignored = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    errors: list[str] = []
    for path in sorted(set(filter(None, f"{visible}\0{ignored}".split("\0")))):
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        suffix = Path(normalized).suffix.casefold()
        protected_root = parts[0].casefold() in PROTECTED_IMPORT_ROOTS
        root_file = len(parts) == 1
        package_artifact = _is_top_level_package_artifact(parts, normalized)
        ordinary_cache = "__pycache__" in parts
        python_shadow = _has_python_shadow_suffix(normalized) and not ordinary_cache
        launcher = (protected_root or root_file) and _is_executable_launcher(
            root / Path(*parts), suffix
        )
        if (protected_root or root_file or package_artifact) and (
            python_shadow or launcher or package_artifact
        ):
            errors.append(f"untracked import-shadowing file is forbidden: {normalized}")
    return errors


def validate(
    expected_sha: str,
    root: Path = ROOT,
    *,
    proof_mode: str = "candidate",
) -> list[str]:
    """Prove that HEAD, the index, and every tracked worktree file are immutable."""
    if _BOOTSTRAP_ERRORS:
        return list(_BOOTSTRAP_ERRORS)
    if proof_mode not in PROOF_MODES:
        return ["proof mode must be candidate or restored-baseline"]
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        return [f"expected {proof_mode} SHA must be exactly 40 hexadecimal characters"]
    try:
        head = _git(root, "rev-parse", "HEAD")
        content_errors = _tracked_content_errors(root)
        shadow_errors = _untracked_shadow_errors(root)
    except RuntimeError as exc:
        return [str(exc)]
    errors: list[str] = []
    if head.casefold() != expected_sha.casefold():
        errors.append(f"checked-out HEAD does not equal the expected {proof_mode} SHA")
    errors.extend(content_errors)
    errors.extend(shadow_errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--proof-mode", choices=sorted(PROOF_MODES), default="candidate")
    args = parser.parse_args()
    errors = validate(args.expected_sha, proof_mode=args.proof_mode)
    print(
        json.dumps(
            {
                "status": "PASS" if not errors else "FAIL",
                "proof_mode": args.proof_mode,
                "expected_sha": args.expected_sha.casefold(),
                "errors": errors,
            },
            indent=2,
        )
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
