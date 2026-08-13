from __future__ import annotations

import json
from pathlib import Path

from integrations.product_proof.service import ProductProofTechnicalAudit


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> Path:
    payload = {
        "responses": {
            "https://example.com/a": {
                "status_code": 200,
                "headers": {"Content-Type": "text/html"},
                "body": "<html><head><title></title><meta name=\"keywords\" content=\"x\"></head><body><h1>A</h1><p>Alpha service page with enough content to avoid soft 404.</p><a href=\"/b\">B</a><a href=\"/c\">C</a></body></html>",
            },
            "https://example.com/b": {
                "status_code": 200,
                "headers": {"Content-Type": "text/html; charset=utf-8"},
                "body": "<html><head><title>Services</title><meta name=\"description\" content=\"Same generic service description.\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><link rel=\"canonical\" href=\"https://example.com/b\"></head><body><h1>B</h1><p>Beta service page with specific proof.</p></body></html>",
            },
            "https://example.com/c": {
                "status_code": 200,
                "headers": {"Content-Type": "text/html; charset=utf-8"},
                "body": "<html><head><title>Services</title><meta name=\"description\" content=\"Same generic service description.\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><link rel=\"canonical\" href=\"https://example.com/c\"></head><body><h1>C</h1><p>Gamma service page with specific proof.</p></body></html>",
            },
            "https://example.com/robots.txt": {
                "status_code": 404,
                "headers": {"Content-Type": "text/plain"},
                "body": "",
            },
        }
    }
    path = tmp_path / "head-fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_product_proof_head_metadata_rules_emit_expected_findings(tmp_path: Path):
    out = tmp_path / "out"
    result = ProductProofTechnicalAudit(
        claim_registry=ROOT / "knowledge" / "seo-claim-registry.json"
    ).run(
        url="https://example.com/a",
        output_dir=out,
        fixture_path=_fixture(tmp_path),
        max_urls=10,
    )
    assert result.status == "complete"

    findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
    finding_ids = {row["id"] for row in findings}
    assert "head-title-missing" in finding_ids
    assert "head-title-duplicated" in finding_ids
    assert "meta-description-missing" in finding_ids
    assert "meta-description-duplicated" in finding_ids
    assert "viewport-missing" in finding_ids
    assert "canonical-missing" in finding_ids
    assert "deprecated-head-metadata" in finding_ids
    assert "social-metadata-incomplete" in finding_ids


def test_head_metadata_fixture_documents_expected_findings():
    payload = json.loads(
        (ROOT / "examples" / "bad-seo-fixtures" / "head-metadata-fixtures.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["fixture_is_live_proof"] is False
    expected = {
        finding
        for fixture in payload["fixtures"]
        for finding in fixture["expected_findings"]
    }
    assert "head-title-missing" in expected
    assert "deprecated-head-metadata" in expected
