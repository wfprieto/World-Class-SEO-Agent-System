from __future__ import annotations

import copy

import pytest

from runtime.evidence_binding import (
    normalize_legacy_output,
    validate_evidence_binding,
)


def _output() -> dict:
    return {
        "contract_version": "2.0.0",
        "execution_state": "COMPLETE",
        "summary": "Clicks declined 32%.",
        "impact": "The affected page is https://example.test/page.",
        "follow_up": "Review after deployment.",
        "risks": [],
        "dependencies": [],
        "acceptance_criteria": [],
        "verification": [],
        "evidence": [
            {
                "id": "gsc-1",
                "source": "gsc.csv",
                "type": "first_party_data",
                "date_checked": "2026-08-01",
                "notes": "Supplied export.",
                "state": "CURRENT",
            }
        ],
        "findings": [
            {
                "id": "finding-1",
                "finding": "Clicks declined 32%.",
                "affected_scope": "https://example.test/page",
                "evidence_refs": ["gsc-1"],
            }
        ],
        "recommended_actions": [],
        "material_claims": [
            {
                "claim_id": "claim-1",
                "claim_type": "numeric",
                "statement": "Clicks declined 32% on https://example.test/page.",
                "bound_fields": [
                    "summary",
                    "impact",
                    "findings[0].finding",
                    "findings[0].affected_scope",
                ],
                "evidence_refs": ["gsc-1"],
                "evidence_state": "AVAILABLE",
                "inference": False,
            }
        ],
    }


@pytest.mark.parametrize("field", ["contract_version", "execution_state", "material_claims"])
def test_current_outputs_require_explicit_evidence_contract_fields(field: str) -> None:
    output = _output()
    output.pop(field)
    errors = validate_evidence_binding(output)
    assert any(field in error for error in errors)


@pytest.mark.parametrize("duplicate", ["id", "source"])
def test_duplicate_evidence_identity_fails_closed(duplicate: str) -> None:
    output = _output()
    second = copy.deepcopy(output["evidence"][0])
    second["id"] = "gsc-2"
    second["source"] = "ga4.csv"
    second[duplicate] = output["evidence"][0][duplicate]
    output["evidence"].append(second)
    assert any(
        f"duplicate evidence {duplicate}" in error
        for error in validate_evidence_binding(output)
    )


def test_finding_id_and_refs_are_unique_and_known() -> None:
    output = _output()
    output["findings"].append(copy.deepcopy(output["findings"][0]))
    output["findings"][0]["evidence_refs"] = ["gsc-1", "gsc-1", "missing"]
    errors = validate_evidence_binding(output)
    assert any("duplicate finding id" in error for error in errors)
    assert any("repeats evidence reference" in error for error in errors)
    assert any("finding finding-1 references unknown evidence: missing" in error for error in errors)


def test_material_claim_refs_are_unique_known_and_not_stronger_than_evidence() -> None:
    output = _output()
    output["evidence"][0]["state"] = "STALE"
    output["material_claims"][0]["evidence_refs"] = ["gsc-1", "gsc-1", "missing"]
    errors = validate_evidence_binding(output)
    assert any("repeats evidence reference" in error for error in errors)
    assert any("references unknown evidence: missing" in error for error in errors)
    assert any("AVAILABLE is stronger than referenced evidence state STALE" in error for error in errors)


def test_invalid_declared_states_fail_closed_without_crashing() -> None:
    output = _output()
    output["execution_state"] = "DONE"
    output["evidence"][0]["state"] = "UNKNOWN"
    output["material_claims"][0]["evidence_state"] = "PROVEN"

    errors = validate_evidence_binding(output)

    assert "execution_state is invalid" in errors
    assert "evidence[0].state is invalid" in errors
    assert "material_claims[0].evidence_state is invalid" in errors


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("risks", ["Revenue exposure is $500."], "$500"),
        ("dependencies", ["Inspect https://example.test/dependency."], "https://example.test/dependency."),
        ("acceptance_criteria", ["Validate 12 URLs."], "12"),
        ("verification", ["Recheck 40%."], "40%"),
    ],
)
def test_every_rendered_material_field_is_scanned(
    field: str, value: list[str], token: str
) -> None:
    output = _output()
    output[field] = value
    assert any(
        token in error and field in error and "not explicitly bound" in error
        for error in validate_evidence_binding(output)
    )


def test_token_coincidence_does_not_replace_explicit_field_binding() -> None:
    output = _output()
    output["material_claims"][0]["bound_fields"] = ["summary"]

    errors = validate_evidence_binding(output)

    assert any("impact" in error and "https://example.test/page" in error for error in errors)
    assert any(
        "findings[0].affected_scope" in error and "https://example.test/page" in error
        for error in errors
    )


def test_current_claims_reject_missing_duplicate_or_unknown_bound_fields() -> None:
    output = _output()
    output["material_claims"][0]["bound_fields"] = []
    assert any("bound_fields is required" in error for error in validate_evidence_binding(output))

    output = _output()
    output["material_claims"][0]["bound_fields"] = ["summary", "summary", "scores.fake"]
    errors = validate_evidence_binding(output)
    assert any("repeats bound field" in error for error in errors)
    assert any("unknown material field: scores.fake" in error for error in errors)


def test_legacy_compatibility_requires_explicit_partial_unverified_normalization() -> None:
    legacy = _output()
    legacy.pop("contract_version")
    legacy.pop("execution_state")
    legacy.pop("material_claims")
    legacy["evidence"][0].pop("state")

    assert validate_evidence_binding(legacy)
    normalized = normalize_legacy_output(legacy)

    assert normalized["contract_version"] == "1.0.0"
    assert normalized["execution_state"] == "PARTIAL"
    assert normalized["legacy_unverified"] is True
    assert normalized["material_claims"] == []
    assert normalized["evidence"][0]["state"] == "UNVERIFIED"
    assert validate_evidence_binding(normalized) == []
