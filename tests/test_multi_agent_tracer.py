from __future__ import annotations

from evaluation.tracer.run_tracer import evaluate


def test_seeded_multi_agent_tracer_returns_go():
    report = evaluate()
    assert report["verdict"] == "GO"
    assert report["improvement_count"] >= 2
    assert len(report["fixtures"]) == 3
    assert all(all(item["checks"].values()) for item in report["fixtures"])
