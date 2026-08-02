from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.tracer.run_tracer import DEFAULT_FIXTURES, evaluate


def test_seeded_multi_agent_tracer_returns_go():
    report = evaluate()
    assert report["verdict"] == "GO"
    assert report["improvement_count"] >= 2
    assert len(report["fixtures"]) == 3
    assert all(all(item["checks"].values()) for item in report["fixtures"])


@pytest.mark.parametrize("mutation", ["missing", "malformed"])
def test_seeded_conflict_requires_valid_structured_polarity(
    tmp_path: Path,
    mutation: str,
) -> None:
    payload = json.loads(DEFAULT_FIXTURES.read_text(encoding="utf-8"))
    finding = payload["fixtures"][0]["outputs"][0]["findings"][0]
    if mutation == "missing":
        finding.pop("action_polarity")
    else:
        finding["action_polarity"] = {"target": "", "polarity": "ENABLE"}
    fixture = tmp_path / "mutated-tracer-fixtures.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    report = evaluate(fixture)

    assert report["verdict"] == "NO_GO"
    assert report["fixtures"][0]["checks"]["expected_conflicts"] is False
