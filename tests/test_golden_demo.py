from __future__ import annotations

import json
from pathlib import Path

from seoctl.audit_cli import run

ROOT = Path(__file__).resolve().parents[1]


def test_golden_demo_contract_matches_cli_output(tmp_path: Path) -> None:
    contract = json.loads(
        (ROOT / "examples" / "golden-demo" / "expected-output-contract.json").read_text(
            encoding="utf-8"
        )
    )
    output = tmp_path / "golden-demo"
    payload, code = run(
        [
            "audit",
            "technical",
            "--url",
            "https://example.com/",
            "--fixture",
            str(ROOT / contract["fixture"]),
            "--output",
            str(output),
            "--max-urls",
            "20",
        ]
    )

    assert code == 0
    assert payload["status"] == contract["expected"]["status"]
    assert payload["data"]["evidence_mode"] == contract["expected"]["evidence_mode"]
    assert payload["data"]["pages_crawled"] == contract["expected"]["pages_crawled"]
    assert payload["data"]["findings"] == contract["expected"]["findings"]
    assert payload["data"]["critical_findings"] == contract["expected"]["critical_findings"]
    assert payload["data"]["agents_executed"] == contract["expected"]["agents_executed"]
    assert (
        payload["data"]["trust_summary"]["external_changes_made"]
        == contract["expected"]["external_changes_made"]
    )
    assert (
        payload["data"]["trust_summary"]["unsupported_material_findings"]
        == contract["expected"]["unsupported_material_findings"]
    )

    manifest = json.loads((output / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["fixture_is_live_proof"] is contract["expected"]["fixture_is_live_proof"]
    for artifact in contract["artifacts"]:
        assert (output / artifact).is_file(), artifact


def test_quickstart_points_to_golden_demo_contract() -> None:
    quickstart = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
    demo = (ROOT / "examples" / "golden-demo" / "README.md").read_text(encoding="utf-8")
    command = json.loads(
        (ROOT / "examples" / "golden-demo" / "expected-output-contract.json").read_text(
            encoding="utf-8"
        )
    )["command"]

    assert command in quickstart
    assert command in demo
    assert "does not prove live rankings" in quickstart.lower()
    assert "does not prove live rankings" in demo.lower()
