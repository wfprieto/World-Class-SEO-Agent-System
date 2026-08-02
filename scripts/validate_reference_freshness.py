"""Validate reference metadata, source coverage, anchors, and freshness windows."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "knowledge" / "reference-registry.json"
CATALOG = ROOT / "skills" / "skill-catalog.json"
WINDOWS = {"volatile": 45, "quarterly": 140, "annual": 400, "stable": 800}


def _content_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _source_errors(pack_id: str, sources: object) -> list[str]:
    if not isinstance(sources, list) or not sources:
        return [f"{pack_id} requires primary_sources"]
    return [
        f"{pack_id} has invalid primary source URL"
        for source in sources
        if (parsed := urlsplit(str(source))).scheme != "https" or not parsed.hostname
    ]


def _pack_errors(pack_id: str, pack: dict, *, today: date, root: Path) -> list[str]:
    failures: list[str] = []
    freshness_class = str(pack.get("freshness_class", ""))
    freshness_window = WINDOWS.get(freshness_class)
    if freshness_window is None:
        failures.append(f"{pack_id} has invalid freshness_class")
    verified: date | None = None
    try:
        verified = date.fromisoformat(str(pack["verified_at"]))
    except (KeyError, ValueError):
        failures.append(f"{pack_id} has invalid verified_at")
    if verified is not None:
        if verified > today:
            failures.append(f"{pack_id} verified_at is in the future")
        elif freshness_window is not None:
            age = (today - verified).days
            if age > freshness_window:
                failures.append(f"{pack_id} is stale by freshness policy ({age} days)")
    if not str(pack.get("owner", "")).strip():
        failures.append(f"{pack_id} requires an owner")
    path = root / str(pack.get("path", ""))
    if not path.is_file():
        failures.append(f"{pack_id} path is missing")
    else:
        expected_digest = str(pack.get("content_sha256", ""))
        if len(expected_digest) != 64 or _content_sha256(path) != expected_digest:
            failures.append(f"{pack_id} content digest does not match its pack")
    failures.extend(_source_errors(pack_id, pack.get("primary_sources", [])))
    return failures


def _entry_errors(
    entries: object,
    *,
    packs: dict,
    known_skills: set[str],
    root: Path,
) -> list[str]:
    if not isinstance(entries, list):
        return ["reference entries must be a list"]
    failures: list[str] = []
    ids = [str(row.get("id", "")) for row in entries if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        failures.append("reference ids must be unique")
    for row in entries:
        if not isinstance(row, dict):
            failures.append("reference entry must be an object")
            continue
        ref_id = str(row.get("id", ""))
        pack_id = str(row.get("pack", ""))
        if pack_id not in packs:
            failures.append(f"{ref_id} references unknown pack {pack_id}")
            continue
        pack = packs[pack_id]
        if not isinstance(pack, dict):
            failures.append(f"{ref_id} references invalid pack {pack_id}")
            continue
        path = root / str(pack.get("path", ""))
        anchor = str(row.get("anchor", ""))
        if path.is_file() and f'id="{anchor}"' not in path.read_text(encoding="utf-8"):
            failures.append(f"{ref_id} anchor is missing")
        unknown = sorted(set(map(str, row.get("affected_skills", []))) - known_skills)
        if unknown:
            failures.append(f"{ref_id} references unknown skills {unknown}")
    return failures


def validate(*, as_of: date | None = None, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    today = as_of or date.today()
    registry_path = root / REGISTRY.relative_to(ROOT)
    catalog_path = root / CATALOG.relative_to(ROOT)
    payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    known_skills = {
        str(skill)
        for category in catalog.get("categories", [])
        for skill in category.get("skills", [])
    }
    packs = payload.get("packs", {})
    if not isinstance(packs, dict):
        return ["reference packs must be an object"]
    for pack_id, pack in packs.items():
        if not isinstance(pack, dict):
            failures.append(f"{pack_id} pack must be an object")
            continue
        failures.extend(_pack_errors(str(pack_id), pack, today=today, root=root))

    failures.extend(
        _entry_errors(
            payload.get("entries", []),
            packs=packs,
            known_skills=known_skills,
            root=root,
        )
    )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    failures = validate(as_of=args.as_of)
    if failures:
        print("Reference validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    print(
        f"Reference validation passed: {len(payload['entries'])} entries "
        f"across {len(payload['packs'])} packs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
