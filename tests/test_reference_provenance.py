from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from scripts.validate_reference_freshness import validate

ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> tuple[Path, dict]:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "skills").mkdir()
    shutil.copy2(ROOT / "knowledge/reference-registry.json", tmp_path / "knowledge")
    shutil.copytree(ROOT / "knowledge/reference-packs", tmp_path / "knowledge/reference-packs")
    shutil.copy2(ROOT / "skills/skill-catalog.json", tmp_path / "skills")
    registry_path = tmp_path / "knowledge/reference-registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return registry_path, payload


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_each_reference_pack_has_independent_date_owner_sources_and_digest() -> None:
    assert validate(as_of=date(2026, 7, 12), root=ROOT) == []


def test_global_registry_date_cannot_refresh_one_stale_pack(tmp_path: Path) -> None:
    path, payload = _fixture(tmp_path)
    payload["registry_updated_at"] = "2026-07-12"
    payload["packs"]["technical-search"]["verified_at"] = "2025-01-01"
    _write(path, payload)

    errors = validate(as_of=date(2026, 7, 12), root=tmp_path)
    assert any("technical-search is stale" in error for error in errors)


def test_pack_content_drift_and_missing_provenance_fail_closed(tmp_path: Path) -> None:
    path, payload = _fixture(tmp_path)
    pack = payload["packs"]["technical-search"]
    pack["content_sha256"] = "0" * 64
    pack["owner"] = ""
    del pack["verified_at"]
    _write(path, payload)

    errors = validate(as_of=date(2026, 7, 12), root=tmp_path)
    assert "technical-search has invalid verified_at" in errors
    assert "technical-search requires an owner" in errors
    assert "technical-search content digest does not match its pack" in errors


def test_pack_validation_accumulates_independent_provenance_defects(
    tmp_path: Path,
) -> None:
    path, payload = _fixture(tmp_path)
    pack = payload["packs"]["technical-search"]
    pack["freshness_class"] = "unknown"
    pack.pop("verified_at")
    pack["owner"] = ""
    pack["path"] = "knowledge/reference-packs/missing.md"
    pack["content_sha256"] = "bad"
    pack["primary_sources"] = []
    _write(path, payload)

    errors = validate(as_of=date(2026, 7, 12), root=tmp_path)

    assert {
        "technical-search has invalid freshness_class",
        "technical-search has invalid verified_at",
        "technical-search requires an owner",
        "technical-search path is missing",
        "technical-search has invalid content_sha256",
        "technical-search requires primary_sources",
    }.issubset(errors)
