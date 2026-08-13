from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from runtime.evidence_binding import normalize_legacy_output

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


def test_agent_output_schema_rejects_implicit_evidence_contract_fields():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    validator = Draft202012Validator(schema)

    for field in ("contract_version", "execution_state", "material_claims"):
        mutated = json.loads(json.dumps(payload))
        mutated.pop(field)
        assert any(field in error.message for error in validator.iter_errors(mutated))


def test_current_material_claim_schema_requires_explicit_bound_fields():
    schema = load_json("schemas/agent-output.schema.json")
    payload = {
        "contract_version": "2.0.0",
        "material_claims": [{
            "claim_id": "claim-1",
            "claim_type": "numeric",
            "statement": "Clicks declined 32%.",
            "evidence_refs": ["gsc-1"],
            "evidence_state": "AVAILABLE",
            "inference": False,
        }],
    }

    errors = list(Draft202012Validator(schema).iter_errors(payload))

    assert any("bound_fields" in error.message for error in errors)


def test_explicit_legacy_normalization_produces_schema_valid_partial_output():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    for field in ("contract_version", "legacy_unverified", "execution_state", "material_claims"):
        payload.pop(field)
    for evidence in payload["evidence"]:
        evidence.pop("id")
        evidence.pop("state")

    normalized = normalize_legacy_output(payload)

    assert list(Draft202012Validator(schema).iter_errors(normalized)) == []


def test_agent_output_schema_rejects_unknown_fields():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    payload["guaranteed_ranking_improvement"] = "50%"
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert any("Additional properties" in error.message for error in errors)


def test_agent_output_schema_rejects_empty_or_missing_finding_ids():
    schema = load_json("schemas/agent-output.schema.json")
    payload = load_json("examples/full-audit-example/agent-output.json")
    validator = Draft202012Validator(schema)

    for invalid_id in ("", "   "):
        mutated = json.loads(json.dumps(payload))
        mutated["findings"][0]["id"] = invalid_id
        assert list(validator.iter_errors(mutated))

    missing = json.loads(json.dumps(payload))
    missing["findings"][0].pop("id")
    errors = list(validator.iter_errors(missing))
    assert any("id" in error.message for error in errors)


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
