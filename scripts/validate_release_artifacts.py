"""Validate generated SBOM and release-manifest integrity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def validate(root: Path, manifest_path: Path, sbom_path: Path) -> list[str]:
    failures: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.5":
        failures.append("SBOM is not CycloneDX 1.5")

    catalog = json.loads(
        (root / "skills" / "skill-catalog.json").read_text(encoding="utf-8")
    )
    expected_skill_count = sum(
        len(row.get("skills", [])) for row in catalog.get("categories", [])
    )
    if manifest.get("command_count", 0) < 1:
        failures.append("manifest command inventory is invalid")
    if manifest.get("skill_count") != expected_skill_count:
        failures.append(
            "manifest skill inventory is invalid: "
            f"expected {expected_skill_count}, got {manifest.get('skill_count')}"
        )

    for row in manifest.get("files", []):
        path = root / row["path"]
        if not path.is_file():
            failures.append(f"manifest file missing: {row['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            failures.append(f"manifest hash mismatch: {row['path']}")
    sbom_record = manifest.get("sbom")
    if (
        sbom_record
        and hashlib.sha256(sbom_path.read_bytes()).hexdigest()
        != sbom_record.get("sha256")
    ):
        failures.append("manifest SBOM hash mismatch")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    args = parser.parse_args()
    failures = validate(args.root.resolve(), args.manifest, args.sbom)
    if failures:
        print("Release artifact validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Release artifact validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
