"""Validate repository version sources without conflating integration and release states."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class VersionSource:
    name: str
    value: str
    path: str


def _changelog_version(root: Path) -> VersionSource:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    if not match:
        raise ValueError("CHANGELOG.md has no semantic version heading")
    return VersionSource("changelog", match.group(1), "CHANGELOG.md")


def _manifest_version(root: Path) -> VersionSource:
    path = root / "docs" / "INTEGRATION-MANIFEST.md"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^\*\*Version:\*\*\s*`?(\d+\.\d+\.\d+)`?", text, re.MULTILINE)
    if not match:
        raise ValueError("docs/INTEGRATION-MANIFEST.md has no Version field")
    return VersionSource("integration_manifest", match.group(1), "docs/INTEGRATION-MANIFEST.md")


def _optional_manifest_versions(root: Path) -> list[VersionSource]:
    sources: list[VersionSource] = []
    candidates = [
        root / "package.json",
        root / "pyproject.toml",
        root / ".claude-plugin" / "plugin.json",
        root / "release-manifest.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            version = payload.get("version")
        else:
            match = re.search(
                r"^version\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']",
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            version = match.group(1) if match else None
        if version:
            sources.append(VersionSource(relative, str(version), relative))
    return sources


def _tag_version(root: Path) -> VersionSource | None:
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
        return None
    value = tag[1:] if tag.startswith("v") else tag
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError(f"release tag is not semantic: {tag}")
    return VersionSource("git_tag", value, "git tag")


def collect(root: Path = ROOT, *, release_mode: bool = False) -> list[VersionSource]:
    sources = [_changelog_version(root), _manifest_version(root), *_optional_manifest_versions(root)]
    if release_mode:
        tag = _tag_version(root)
        if tag is None:
            raise ValueError("release mode requires an exact semantic Git tag")
        sources.append(tag)
    return sources


def validate(root: Path = ROOT, *, release_mode: bool = False) -> list[str]:
    sources = collect(root, release_mode=release_mode)
    versions = {source.value for source in sources}
    if len(versions) > 1:
        detail = ", ".join(f"{source.name}={source.value}" for source in sources)
        return [f"version sources disagree: {detail}"]
    return []


def state_legend() -> dict[str, str]:
    return {
        "integrated_into_main": "Code exists in the canonical main branch.",
        "released_or_tagged": "A reviewed release or semantic tag exists.",
        "published_or_distributed": "A package, plugin, or marketplace artifact is available.",
        "deployed": "A running environment uses the release.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository release-version consistency.")
    parser.add_argument("--release-mode", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    arguments = parser.parse_args()
    try:
        sources = collect(arguments.root, release_mode=arguments.release_mode)
        failures = validate(arguments.root, release_mode=arguments.release_mode)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Release-version validation failed: {exc}")
        return 1
    if failures:
        for failure in failures:
            print(failure)
        return 1
    version = sources[0].value
    print(f"Release-version validation passed: {version}")
    for source in sources:
        print(f"- {source.name}: {source.value} ({source.path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
