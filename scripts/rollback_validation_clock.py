"""Fail-closed validation clock for exact, approved rollback baselines."""

from __future__ import annotations

import hmac
import os
import subprocess
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path

APPROVED_BOUNDARIES = {
    "e8c37abb5e939d4433e42ea8a02af63549ca0010": date(2026, 10, 12),
    "aebd681097bb3c3322da50233e7fe2dc2e5a9144": date(2026, 10, 12),
}


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def effective_as_of(
    root: Path,
    environment: Mapping[str, str] | None = None,
    head_reader: Callable[[Path], str] = _git_head,
) -> date:
    """Use today normally; allow only an exact approved historical baseline/date pair."""
    values = os.environ if environment is None else environment
    requested = values.get("WCSEO_VALIDATION_AS_OF")
    expected = values.get("WCSEO_ROLLBACK_EXPECTED_SHA")
    if requested is None and expected is None:
        return date.today()
    if not requested or not expected:
        raise ValueError("historical validation requires both date and expected rollback SHA")
    boundary = APPROVED_BOUNDARIES.get(expected)
    if boundary is None or requested != boundary.isoformat():
        raise ValueError("historical validation boundary is not approved")
    if not hmac.compare_digest(head_reader(root), expected):
        raise ValueError("repository HEAD does not match the approved rollback baseline")
    return boundary
