from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "bad-seo-fixtures" / "fixtures.json"
DOC = ROOT / "docs" / "BAD-SEO-FIXTURE-PACK.md"

EXPECTED_CATEGORIES = {
    "head-tags",
    "content",
    "indexability",
    "http-status",
    "redirects",
    "structure",
    "performance",
    "compound",
}

ALLOWED_SEVERITIES = {"Critical", "High", "Medium", "Low"}


def _payload() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_bad_seo_fixture_pack_covers_core_failure_classes():
    payload = _payload()
    assert payload["fixture_is_live_proof"] is False
    assert EXPECTED_CATEGORIES <= set(payload["categories"])

    categories = {fixture["category"] for fixture in payload["fixtures"]}
    assert EXPECTED_CATEGORIES <= categories


def test_bad_seo_fixtures_have_expected_findings_with_evidence():
    payload = _payload()
    fixture_ids = [fixture["id"] for fixture in payload["fixtures"]]
    assert len(fixture_ids) == len(set(fixture_ids))

    finding_ids: list[str] = []
    for fixture in payload["fixtures"]:
        assert fixture["url"].startswith("https://fixture.example/")
        assert fixture["inputs"]
        assert fixture["expected_findings"]
        for finding in fixture["expected_findings"]:
            finding_ids.append(finding["id"])
            assert finding["severity"] in ALLOWED_SEVERITIES
            assert finding["evidence_refs"]
            assert finding["recommended_action_category"]

    assert len(finding_ids) == len(set(finding_ids))


def test_bad_seo_fixture_docs_reference_canonical_pack():
    body = DOC.read_text(encoding="utf-8")
    assert "examples/bad-seo-fixtures/fixtures.json" in body
    body_lower = body.lower()
    for category in EXPECTED_CATEGORIES:
        assert category in body_lower
