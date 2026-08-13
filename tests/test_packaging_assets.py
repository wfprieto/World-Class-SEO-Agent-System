from __future__ import annotations

import tomllib
from pathlib import Path

from seoctl.doctor import REQUIRED_ASSETS


ROOT = Path(__file__).resolve().parents[1]


def _data_file_patterns() -> list[str]:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    data_files = payload["tool"]["setuptools"]["data-files"]
    return [pattern for patterns in data_files.values() for pattern in patterns]


def _packaged_relative_paths() -> set[str]:
    paths: set[str] = set()
    for pattern in _data_file_patterns():
        matches = sorted(ROOT.glob(pattern))
        assert matches, f"packaging data-file pattern has no matches: {pattern}"
        paths.update(
            path.relative_to(ROOT).as_posix()
            for path in matches
            if path.is_file() and "__pycache__" not in path.parts
        )
    return paths


def test_system_doctor_required_assets_are_packaged() -> None:
    packaged = _packaged_relative_paths()
    assert set(REQUIRED_ASSETS) <= packaged


def test_static_architecture_source_snapshots_are_packaged() -> None:
    packaged = _packaged_relative_paths()
    expected = {
        "adapters/registry.py",
        "contracts/adapter.py",
        "integrations/google/client.py",
        "runtime/assets.py",
        "security/url_safety.py",
        "seoctl/doctor.py",
    }
    assert expected <= packaged
