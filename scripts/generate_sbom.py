"""Generate a deterministic CycloneDX JSON SBOM from declared and locked dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
import uuid
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def _declared_dependencies(pyproject: Path) -> list[tuple[Requirement, str | None]]:
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    declared: list[tuple[Requirement, str | None]] = [
        (Requirement(str(value)), None) for value in project.get("dependencies", [])
    ]
    for group, values in project.get("optional-dependencies", {}).items():
        declared.extend((Requirement(str(value)), str(group)) for value in values)
    return sorted(declared, key=lambda row: (row[0].name.lower(), row[1] or ""))


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _locked_versions(lock_path: Path) -> dict[str, str]:
    if not lock_path.is_file():
        raise ValueError(f"dependency lock is missing: {lock_path}")
    pins: dict[str, str] = {}
    for raw in lock_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", raw.strip())
        if match:
            pins[_normalized(match.group(1))] = match.group(2)
    return pins


def _project_version(pyproject: Path) -> str:
    return str(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"])


def build_sbom(root: Path = ROOT) -> dict:
    pyproject = root / "pyproject.toml"
    pins = _locked_versions(root / "requirements-dev.txt")
    components = []
    for requirement, optional_group in _declared_dependencies(pyproject):
        name = requirement.name
        version = pins.get(_normalized(name))
        if optional_group is None and version is None:
            raise ValueError(f"required dependency is not resolved in requirements-dev.txt: {name}")
        component: dict[str, Any] = {
            "type": "library",
            "name": name,
            "purl": f"pkg:pypi/{name.lower()}" + (f"@{version}" if version else ""),
            "scope": "optional" if optional_group else "required",
            "properties": [
                {"name": "wcseo:declared_requirement", "value": str(requirement)},
                {
                    "name": "wcseo:resolution",
                    "value": "LOCKED" if version else "DECLARED_OPTIONAL_UNRESOLVED",
                },
            ],
        }
        if version:
            component["version"] = version
        if optional_group:
            component["properties"].append(
                {"name": "wcseo:optional_group", "value": optional_group}
            )
        components.append(component)
    digest = hashlib.sha256(pyproject.read_bytes()).hexdigest()
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"wcseo:{digest}")
    return {"bomFormat":"CycloneDX","specVersion":"1.5","serialNumber":f"urn:uuid:{serial}","version":1,"metadata":{"component":{"type":"application","name":"world-class-seo-agent-system","version":_project_version(pyproject)},"properties":[{"name":"wcseo:pyproject_sha256","value":digest}]},"components":components}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = build_sbom(args.root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote CycloneDX SBOM: {args.out} ({len(payload['components'])} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
