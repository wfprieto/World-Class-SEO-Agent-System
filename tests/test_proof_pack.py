from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "proof-pack" / "proof-pack-manifest.json"

REQUIRED_PROOF_UNITS = {
    "golden-demo-technical-audit",
    "bad-seo-failure-fixtures",
    "anonymized-search-performance-and-cwv",
    "product-proof-intelligence-fixtures",
    "schema-and-report-examples",
}

FORBIDDEN_PRIVACY_TERMS = {
    "oauth token",
    "service-account credentials",
    "private client domains",
    "property ids",
    "account ids",
}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_proof_pack_manifest_covers_required_units() -> None:
    payload = _manifest()
    assert payload["fixture_is_live_proof"] is False
    unit_ids = {unit["id"] for unit in payload["proof_units"]}
    assert REQUIRED_PROOF_UNITS <= unit_ids


def test_proof_pack_files_exist_and_are_validated() -> None:
    for unit in _manifest()["proof_units"]:
        assert unit["target_agents"], unit["id"]
        assert unit["files"], unit["id"]
        assert unit["validation"], unit["id"]
        assert unit["does_not_prove"], unit["id"]
        for relative in unit["files"]:
            assert (ROOT / relative).exists(), f"{unit['id']} missing {relative}"


def test_proof_pack_is_discoverable_and_has_safety_boundary() -> None:
    examples_index = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "examples" / "proof-pack" / "README.md").read_text(encoding="utf-8")
    manifest_text = MANIFEST.read_text(encoding="utf-8")

    assert "proof-pack/" in examples_index
    assert "not evidence of live rankings" in readme.lower()
    assert "automatic website mutation" in manifest_text
    for term in FORBIDDEN_PRIVACY_TERMS:
        assert term in manifest_text.lower()


def test_proof_pack_does_not_overclaim_live_capability() -> None:
    payload = _manifest()
    forbidden_claims = {
        "proves live rankings",
        "proves live indexing",
        "proves live Search Console",
        "proves provider authentication",
        "proves automatic website mutation",
    }
    serialized = json.dumps(payload)
    assert not any(claim in serialized for claim in forbidden_claims)
    for unit in payload["proof_units"]:
        joined_limits = " ".join(unit["does_not_prove"]).lower()
        assert any(
            term in joined_limits
            for term in ("live", "provider", "mutation", "deployment", "legal")
        ), unit["id"]
