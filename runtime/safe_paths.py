"""Canonical path-containment helpers for repository-owned runtime assets."""

from __future__ import annotations

from pathlib import Path


class UnsafeRepositoryPath(ValueError):
    """Raised when a requested repository asset escapes the configured root."""


def resolve_repository_path(
    repo_root: Path,
    relative_path: str,
    *,
    must_exist: bool = True,
    allowed_suffixes: set[str] | None = None,
) -> Path:
    """Resolve a repository-relative path without permitting absolute or symlink escape.

    The caller must provide a relative path. The resolved target must remain below the
    resolved repository root after following symlinks. Optional suffix restrictions can
    further constrain the class of readable asset.
    """

    if not isinstance(relative_path, str) or not relative_path.strip():
        raise UnsafeRepositoryPath("Repository asset path must be a non-empty string.")

    requested = Path(relative_path)
    if requested.is_absolute():
        raise UnsafeRepositoryPath("Absolute repository asset paths are not allowed.")

    root = repo_root.expanduser().resolve()
    candidate = (root / requested).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise UnsafeRepositoryPath("Repository asset path escapes the configured root.")

    if allowed_suffixes is not None and candidate.suffix.lower() not in {
        suffix.lower() for suffix in allowed_suffixes
    }:
        raise UnsafeRepositoryPath(
            f"Repository asset suffix {candidate.suffix or '<none>'!r} is not allowed."
        )

    if must_exist and (not candidate.exists() or not candidate.is_file()):
        raise FileNotFoundError(f"Repository asset does not exist: {relative_path}")

    return candidate
