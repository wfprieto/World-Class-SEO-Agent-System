from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_agent_output_example_conforms_to_schema():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == []


def test_agent_output_schema_rejects_missing_follow_up():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    payload.pop("follow_up")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert any("follow_up" in error.message for error in errors)


def test_agent_output_schema_rejects_unknown_fields():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    payload["guaranteed_ranking_improvement"] = "50%"
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert any("Additional properties" in error.message for error in errors)


def test_session_state_schema_example_conforms():
    schema = load_json("orchestration/session-state.schema.json")
    example = schema["examples"][0]
    errors = list(Draft202012Validator(schema).iter_errors(example))
    assert errors == []


def test_handoff_payload_example_conforms():
    schema = load_json("schemas/handoff-payload.schema.json")
    payload = load_json("examples/schema-validation-examples/handoff-payload.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == []


def test_decision_record_example_conforms():
    schema = load_json("schemas/decision-record.schema.json")
    payload = load_json("examples/schema-validation-examples/decision-record.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == []


def test_rule_update_example_conforms():
    schema = load_json("schemas/rule-update.schema.json")
    payload = load_json("examples/schema-validation-examples/rule-update.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == []
