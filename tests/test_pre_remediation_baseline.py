from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pre_remediation_baseline_is_sanitized_and_records_single_agent_gap():
    payload = json.loads(
        (ROOT / "tests" / "baselines" / "pre-remediation-runtime.json").read_text(encoding="utf-8")
    )
    assert payload["sanitized"] is True
    assert payload["contains_secrets"] is False
    assert payload["totals"] == {
        "requests": 6,
        "support_agents_listed": 16,
        "support_agents_executed": 0,
        "llm_calls": 6,
        "handoffs_emitted": 6,
        "handoffs_consumed": 0,
        "decisions": 0,
    }
