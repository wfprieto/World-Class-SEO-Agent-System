"""Locate canonical repository assets in a source checkout or installed wheel."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_MARKERS = (
    "SYSTEM_SPEC.md",
    "orchestration/capability-registry.json",
    "knowledge/seo-quality-gates.md",
)


def _valid(root: Path) -> bool:
    return all((root / marker).exists() for marker in _MARKERS)


def resolve_asset_root(preferred: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    configured = os.environ.get("WORLD_CLASS_SEO_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    if preferred is not None:
        candidates.append(Path(preferred).expanduser())
    candidates.extend([
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(sys.prefix) / "share" / "world-class-seo",
        Path(sys.base_prefix) / "share" / "world-class-seo",
    ])
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _valid(resolved):
            return resolved
    detail = ", ".join(str(path) for path in seen)
    raise FileNotFoundError(
        "World-Class SEO runtime assets were not found. Set WORLD_CLASS_SEO_ROOT "
        f"or install the wheel with data assets. Checked: {detail}"
    )
