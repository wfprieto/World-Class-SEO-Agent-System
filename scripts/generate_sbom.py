"""Generate a deterministic CycloneDX JSON SBOM for declared Python dependencies."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _declared_dependencies(pyproject: Path) -> list[str]:
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    raw = list(project.get("dependencies", []))
    for values in project.get("optional-dependencies", {}).values():
        raw.extend(values)
    names = []
    for requirement in raw:
        name = str(requirement).split(";", 1)[0].strip()
        for marker in ("[", "<", ">", "=", "!", "~", " "):
            name = name.split(marker, 1)[0]
        if name:
            names.append(name)
    return sorted(set(names), key=str.lower)


def _project_version(pyproject: Path) -> str:
    return str(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"])


def build_sbom(root: Path = ROOT) -> dict:
    pyproject = root / "pyproject.toml"
    components = []
    for name in _declared_dependencies(pyproject):
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = "NOT_INSTALLED"
        purl = f"pkg:pypi/{name.lower()}" + (f"@{version}" if version != "NOT_INSTALLED" else "")
        components.append({"type":"library","name":name,"version":version,"purl":purl,"properties":[{"name":"wcseo:declared","value":"true"}]})
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
