"""Behavioral guardrails for the script quality extraction."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import validate_remediation_program as remediation
from scripts.architecture_network_inventory import EXPECTED_NETWORK_TRANSPORTS
from scripts.run_improvement_cycle import validate_reviewer_independence
from scripts.validate_repository_governance import provider_state_errors

ROOT = Path(__file__).resolve().parents[1]


def test_llm_transport_inventory_binds_the_canonical_numeric_handlers() -> None:
    assert EXPECTED_NETWORK_TRANSPORTS.get("adapters/llm_transport.py") == {
        "policy": "CONFIGURED_LLM_PINNED_TRANSPORT",
        "delegates_to": "security.pinned_http.PinnedHTTPHandler + security.pinned_http.PinnedHTTPSHandler",
    }


@pytest.mark.parametrize(
    ("path", "delegate"),
    [
        ("integrations/google/oauth.py", "integrations.google.oauth.GoogleOAuthProvider"),
        ("integrations/google/transport.py", "integrations.google.transport._NoCrossHostRedirects"),
    ],
)
def test_extracted_google_network_modules_keep_exact_transport_policy(
    path: str, delegate: str
) -> None:
    assert EXPECTED_NETWORK_TRANSPORTS.get(path) == {
        "policy": "GOOGLE_API_BOUNDED_HTTP", "delegates_to": delegate
    }


def test_comparator_preserves_both_public_cli_forms() -> None:
    for arguments in (["scripts/inventory_comparator.py"], ["-m", "scripts.inventory_comparator"]):
        result = subprocess.run(
            [sys.executable, "-B", "-E", "-S", *arguments, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, result.stderr
        assert "Validate the comparative SEO-system rebaseline." in result.stdout


def test_evidence_rejection_order_and_immutable_bytes(tmp_path: Path) -> None:
    evidence = {"class": "SOURCE", "ref": "absent::section", "commit": "wrong", "status": "FAIL"}
    assert remediation._evidence_errors(evidence, "verified", tmp_path, "phase") == [
        "phase evidence is not bound to verified_commit or an immutable ancestor",
        "phase evidence does not exist at verified_commit: absent::section",
        "phase evidence absent::section is not passing",
    ]
    evidence.update({"class": "CI", "ref": "https://example.invalid/run", "provenance": {}})
    assert remediation._evidence_errors(evidence, "verified", tmp_path, "phase") == [
        "phase evidence is not bound to verified_commit or an immutable ancestor",
        "phase CI evidence is not a canonical repository run: https://example.invalid/run",
        "phase CI provenance repository is not authenticated",
        "phase CI provenance workflow is not authenticated",
        "phase CI provenance conclusion is not authenticated",
        "phase CI provenance head_sha is not the bound evidence commit",
        "phase CI provenance has no successful job inventory",
        "phase evidence https://example.invalid/run is not passing",
    ]


def test_program_rules_keep_ordered_fail_closed_diagnostics(tmp_path: Path) -> None:
    program = {
        "phases": [],
        "direct_merge_permitted": True,
        "failures": [{"id": "f"}, {"id": "f"}],
        "learning_records": [{"id": "l", "failure_id": "unknown"}, {"id": "l"}],
        "audit_findings": [{"id": "a", "source_refs": ["missing"]}, {"id": "a"}],
    }
    assert remediation._validate_program_rules(program, tmp_path) == [
        f"phase order must be {remediation.PHASE_IDS}; found []",
        "program must preserve explicit exclusions: ['public packaging and release maturity', 'real-world SEO effectiveness and external reproduction']",
        "the remediation program can never authorize direct merge",
        "failure ids must be unique",
        "learning record ids must be unique",
        "audit finding ids must be unique",
        "audit finding a references missing source missing",
        "learning record l references unknown failure unknown",
    ]


def test_reviewer_independence_preserves_identity_then_per_verdict_order() -> None:
    verdict = {"reviewer_id": "same", "context_id": "builder", "role": "wrong"}
    errors = validate_reviewer_independence(
        [verdict, copy.deepcopy(verdict)],
        builder_context_id="builder",
        evidence_package_hash="hash",
    )
    assert errors[:4] == [
        "reviewer roles must be ['SENIOR_SCRUMMASTER_3', 'VP_ENGINEERING']; found ['wrong']",
        "reviewer ids must be distinct",
        "reviewer context ids must be distinct",
        "reviewer context cannot equal the builder context",
    ]
    assert (
        errors[4:]
        == [
            "same must explicitly declare is_builder=false",
            "same must submit before seeing the other verdict",
            "same reviewed a different evidence package",
            "same must provide at least three objections",
        ]
        * 2
    )


def test_provider_missing_ruleset_retains_early_return_order() -> None:
    assert provider_state_errors({}, {"repository": "canonical"}) == [
        "governance contract is missing the normalized ruleset",
        "provider snapshot schema_version is unsupported",
    ]


@pytest.mark.parametrize(
    "field", ["strategy", "candidate_selector", "commit_range", "revert_order"]
)
def test_durable_rollback_cannot_accept_static_snapshot_fields(tmp_path: Path, field: str) -> None:
    program = json.loads(remediation.PROGRAM_PATH.read_text(encoding="utf-8"))
    payload = json.loads(
        (ROOT / "evaluation/remediation/phase0-rollback-evidence.json").read_text()
    )
    assert remediation._rollback_evidence_errors(payload, program, tmp_path, "rollback") == []
    payload[field] = "static-or-stale"
    assert remediation._rollback_evidence_errors(payload, program, tmp_path, "rollback") == [
        f"rollback {field} is stale or unsafe"
    ]
