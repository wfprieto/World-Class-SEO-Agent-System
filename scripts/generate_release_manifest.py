"""Generate a reproducible release manifest with repository file hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".pytest_cache", "__pycache__", ".seo-cache", "outputs", "build", "dist"}


def _tracked(root: Path) -> list[Path]:
    try:
        raw = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=root,
            timeout=20,
            stderr=subprocess.DEVNULL,
        )
        return [root / item for item in raw.decode().split("\0") if item]
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return [
            path
            for path in root.rglob("*")
            if path.is_file() and not any(part in EXCLUDED for part in path.parts)
        ]


def _version(root: Path) -> str:
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def build_manifest(root: Path = ROOT, *, sbom_path: Path | None = None) -> dict:
    files = []
    for path in sorted(_tracked(root), key=lambda item: item.relative_to(root).as_posix()):
        if not path.exists() or any(part in EXCLUDED for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    registry = json.loads(
        (root / "seoctl" / "command-registry.json").read_text(encoding="utf-8")
    )
    skills = json.loads(
        (root / "skills" / "skill-catalog.json").read_text(encoding="utf-8")
    )
    payload = {
        "schema_version": "1.0.0",
        "project": "world-class-seo-agent-system",
        "version": _version(root),
        "supported_python": ["3.11", "3.13"],
        "command_count": len(registry.get("commands", [])),
        "skill_count": sum(
            len(row.get("skills", [])) for row in skills.get("categories", [])
        ),
        "files": files,
    }
    if sbom_path and sbom_path.is_file():
        payload["sbom"] = {
            "path": str(sbom_path),
            "sha256": hashlib.sha256(sbom_path.read_bytes()).hexdigest(),
        }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--sbom", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = build_manifest(args.root.resolve(), sbom_path=args.sbom)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote release manifest: {args.out} ({len(payload['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
