"""Synthetic full evidence fixtures: semantic success is never issuer authentication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import timedelta

import pytest
from test_publication_benchmark import (
    CANDIDATE,
    NOW,
    benchmark_package,
    pack_record,
    rewrite_records,
)
from test_publication_subject import payloads

from adapters.mcp_extensions import REGISTRY
from scripts import publication_policy as policy
from scripts.publication_evidence import execution_seal, parse_evidence
from scripts.publication_subject import build_subject, parse_subject, subject_files
from tests.publication_evidence_fixtures import live_fixture

LIVE_IDS = ["gsc-live", "ga4-live", "render-installable", "commoncrawl-authority",
            "domain-history", "youtube-search", "bing-indexnow"]
PROVIDERS = ["google-search-console", "google-analytics-data", "authorized-public-web",
             "rdap-common-crawl", "rdap-common-crawl", "youtube-data", "indexnow"]
LIVE_COMMANDS = [["google.gsc-query", "google.gsc-aggregate"], ["google.ga4-report"],
                 ["render.page", "render.screenshot"], ["links.commoncrawl"],
                 ["domain.history"], ["media.youtube-search"], ["indexnow.submit"]]
COMMANDS = {
    "cli_help": ["--help"], "registry": ["--registry-check"],
    "integrations": ["integrations", "list"], "knowledge": ["knowledge", "validate"],
    "doctor": ["system", "doctor"], "humanize": ["content", "humanize", "--input", "input.txt",
                                                            "--output", "output.txt"],
    "technical_fixture": ["audit", "technical", "--url", "https://example.com/", "--fixture",
                          "site-fixture.json", "--output", "audit", "--max-urls", "20"],
}




def evidence_package():
    benchmark, records = benchmark_package()
    raw_subject = build_subject(
        commit=CANDIDATE, tree="b" * 40, version="1.7.1", ci_run_id=1, ci_attempt=1,
        prepare_run_id=2, prepare_attempt=1, prepared_at=NOW - timedelta(minutes=5),
        payloads=payloads(),
    )
    subject = parse_subject(raw_subject, now=NOW)
    digest = hashlib.sha256(raw_subject).hexdigest()
    bound = {"candidate_commit": CANDIDATE, "prepared_subject_sha256": digest}
    observations, prerequisite_refs, capability_records = live_fixture(records, bound, NOW)
    wheel = next(row for row in subject_files(subject).values() if row["role"] == "wheel")
    context = {"repository_id": 987, "owner_id": 876, "actor_id": 765,
               "run_id": 43, "run_attempt": 1}
    execution_id = "github:987:run:43:attempt:1"
    environment = pack_record(records, {
        **bound, "kind": "reproduction_environment", **context, "execution_id": execution_id,
        "outside_source": True, "python_version": "3.13.4", "os": "synthetic-test-os",
        "created_at": (NOW - timedelta(seconds=45)).isoformat(),
        "installed_wheel_sha256": wheel["sha256"],
    })
    commands = []
    for command_id, arguments in COMMANDS.items():
        commands.append(pack_record(records, {
            **bound, "kind": "reproduction_command", "execution_id": execution_id,
            "wheel_sha256": wheel["sha256"], "command_id": command_id,
            "argv": ["python", "-m", "seoctl", *arguments], "exit_code": 0,
            "executed_at": NOW.isoformat(), "stdout_sha256": "3" * 64,
            "stderr_sha256": hashlib.sha256(b"").hexdigest(), "output_bytes": 1,
        }))
    capability_records.append(("documentation-install-success", "external_reproduction", commands))
    community = pack_record(records, {
        **bound, "kind": "community_observation", "execution_id": execution_id,
        "observed_at": NOW.isoformat(), "metric": "independent-usage-observation", "value": 1,
        "events": [{"repository_id": policy.REPOSITORY_ID, "actor_id": 765, "event_id": 11,
                    "event_type": "issue", "url_sha256": "4" * 64}],
    })
    capability_records.append(("community-infrastructure", "external_reproduction", [community]))
    capabilities = []
    for capability, gate, refs in capability_records:
        proof = pack_record(records, {
            **bound, "kind": "capability_closure", "id": capability,
            "status": "VERIFIED_PARITY", "execution_gate": gate,
            "observed_at": NOW.isoformat(), "observations": refs,
        })
        capabilities.append({"id": capability, "status": "VERIFIED_PARITY", "evidence_refs": [proof]})
    capabilities.append({"id": "release-distribution", "status": "GAP_OPEN", "evidence_refs": []})
    executions = {gate: {"authority_index": 0, "run_id": 43 if gate == "external_reproduction" else 41,
                         "run_attempt": 1, "artifact_id": 100, "artifact_sha256": "5" * 64,
                         "member_name": "result.json", "member_sha256": "6" * 64}
                  for gate in policy.EXECUTION_GATES}
    data = {"schema_version": "1.0.0", **bound, "comparator_commit": policy.COMPARATOR_COMMIT,
            "executions": executions, "benchmark": benchmark,
            "live": {**bound, "mode": "AUTHORIZED_LIVE", "observations": observations,
                     "prerequisites": prerequisite_refs},
            "external_reproduction": {**bound, "mode": "INDEPENDENT_EXTERNAL",
                "wheel_sha256": wheel["sha256"], "execution": context,
                "environment": environment, "commands": commands},
            "capabilities": capabilities}
    return data, records, subject, digest


def validate_package(data, records, subject, digest, **kwargs):
    """Explicit future-contract test only; actual current Bing still blocks below."""
    with pytest.MonkeyPatch.context() as scoped:
        scoped.setitem(REGISTRY, "bing-webmaster", replace(REGISTRY["bing-webmaster"], live_state="CONFIGURABLE"))
        return parse_evidence(json.dumps(data).encode(), records, subject,
                              subject_sha256=digest, now=NOW, **kwargs)


def test_counterfactual_full_data_is_semantically_checked_but_does_not_become_authority():
    data, records, subject, digest = evidence_package()
    assert validate_package(data, records, subject, digest) == data
    assert "authenticated" not in data and "release_decision" not in data
    assert validate_package(data, records, subject, digest, final=True) == data


def test_actual_current_bing_contract_blocks_even_otherwise_typed_full_data():
    data, records, subject, digest = evidence_package()
    with pytest.raises(ValueError, match="Bing source contract"):
        parse_evidence(json.dumps(data).encode(), records, subject, subject_sha256=digest, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("candidate_commit", "b" * 40), ("prepared_subject_sha256", "0" * 64),
    ("comparator_commit", "c" * 40), ("release_decision", "APPROVED"),
])
def test_top_level_source_or_contract_substitution_is_rejected(field, value):
    data, records, subject, digest = evidence_package()
    data[field] = value
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)


@pytest.mark.parametrize("mutation", ["fixture", "builder", "failed-command", "missing-capability",
                                    "unreferenced-record", "pointer-bool", "raw-subject-digest"])
def test_observed_execution_or_completeness_failures_are_not_passed(mutation):
    data, records, subject, digest = evidence_package()
    if mutation == "fixture":
        data["live"]["mode"] = "FIXTURE"
    elif mutation == "builder":
        data["external_reproduction"]["execution"]["owner_id"] = policy.OWNER_ID
    elif mutation == "failed-command":
        reference = data["external_reproduction"]["commands"][0]
        raw = json.loads(records[reference["path"]])
        records.pop(reference["path"])
        data["external_reproduction"]["commands"][0] = pack_record(records, {**raw, "exit_code": 1})
    elif mutation == "missing-capability":
        data["capabilities"].pop(0)
    elif mutation == "unreferenced-record":
        pack_record(records, {"unreferenced": "record"})
    elif mutation == "pointer-bool":
        data["executions"]["external_reproduction"]["run_id"] = True
    else:
        digest = "f" * 64
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)


def test_live_response_requires_real_referenced_normalized_data_and_consent():
    data, records, subject, digest = evidence_package()
    reference = data["live"]["observations"][0]
    observation = json.loads(records[reference["path"]])
    authorization = observation["authorization"]
    raw = json.loads(records[authorization["path"]])
    records.pop(authorization["path"])
    observation["authorization"] = pack_record(records, {**raw, "max_requests": 0})
    records.pop(reference["path"])
    data["live"]["observations"][0] = pack_record(records, observation)
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)


def expected_seal(data, records, gate, context):
    live = gate == "live_authorized_smokes"
    benchmark = gate == "seven_archetype_benchmark"
    section = "benchmark" if benchmark else "live" if live else "external_reproduction"
    ids = set(LIVE_IDS) if live else {"documentation-install-success", "community-infrastructure"}
    capabilities = [] if benchmark else sorted(
        [row for row in data["capabilities"] if row["id"] in ids], key=lambda row: row["id"])
    inventory = []
    for path, raw in sorted(records.items()):
        record = json.loads(raw)
        kind = record["kind"]
        relevant = (kind.startswith("benchmark_") or kind == "finding_evidence") if benchmark else (
            kind.startswith("live_") or kind in {"normalized_observation", "capability_prerequisite", "command_input"}) if live else (
            kind.startswith("reproduction_") or kind == "community_observation")
        if relevant or (not benchmark and kind == "capability_closure" and record["id"] in ids):
            inventory.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    body = {"section": data[section], "capabilities": capabilities, "records": inventory}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"schema_version": "1.0.0", "gate": gate, "candidate_commit": CANDIDATE,
            "prepared_subject_sha256": data["prepared_subject_sha256"],
            "execution_context": context, "evidence_sha256": hashlib.sha256(raw).hexdigest()}


@pytest.mark.parametrize("gate", sorted(policy.EXECUTION_GATES))
def test_execution_seal_covers_gate_capabilities_and_all_transitive_exact_record_bytes(gate):
    data, records, _, _ = evidence_package()
    context = {**data["external_reproduction"]["execution"],
               "run_id": data["executions"][gate]["run_id"]}
    assert execution_seal(data, records, gate=gate, execution_context=context) == expected_seal(
        data, records, gate, context)


@pytest.mark.parametrize("mutation", ["record-bytes", "context-bool", "context-mismatch", "unknown-gate"])
def test_execution_seal_rejects_unbound_data_or_non_provider_context(mutation):
    data, records, _, _ = evidence_package()
    gate = "external_reproduction"
    context = dict(data[gate]["execution"])
    if mutation == "record-bytes":
        records[data[gate]["commands"][0]["path"]] = b'{"tampered":true}'
    elif mutation == "context-bool":
        context["run_attempt"] = True
    elif mutation == "context-mismatch":
        context["owner_id"] += 1
    else:
        gate = "arbitrary-producer"
    with pytest.raises(ValueError):
        execution_seal(data, records, gate=gate, execution_context=context)


def test_shared_live_authorization_enforces_cumulative_request_budget():
    data, records, subject, digest = evidence_package()
    data, records = rewrite_records(data, records, lambda row: {
        **row, "max_requests": 1
    } if row["kind"] == "live_authorization" and row["target"]["kind"] == "gsc_property" else None)
    with pytest.raises(ValueError, match="cumulative"):
        validate_package(data, records, subject, digest)


def test_capability_status_must_be_a_legal_scalar_string():
    data, records, subject, digest = evidence_package()
    data["capabilities"][0]["status"] = []
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)


def test_actual_cost_requires_explicit_consent_even_for_normally_free_profiles():
    data, records, subject, digest = evidence_package()

    def spend(row):
        if row["kind"] == "live_authorization":
            return {**row, "max_cost_micros": 2}
        if row["kind"] == "normalized_observation" and row["provider_id"] == "google-search-console":
            return {**row, "cost_micros": 1}
        return None

    data, records = rewrite_records(data, records, spend)
    with pytest.raises(ValueError, match="cost approval"):
        validate_package(data, records, subject, digest)


def test_write_profile_cannot_be_closed_by_an_observation_with_no_actual_write():
    data, records, subject, digest = evidence_package()
    data, records = rewrite_records(data, records, lambda row: {
        **row, "write_performed": False
    } if row["kind"] == "normalized_observation" and row["provider_id"] == "indexnow" else None)
    with pytest.raises(ValueError, match="actual write"):
        validate_package(data, records, subject, digest)


def test_environment_context_rejects_boolean_attempt_even_when_python_compares_it_equal():
    data, records, subject, digest = evidence_package()
    data, records = rewrite_records(data, records, lambda row: {
        **row, "run_attempt": True
    } if row["kind"] == "reproduction_environment" else None)
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)


@pytest.mark.parametrize("identity", ["gsc-live", "documentation-install-success", "community-infrastructure"])
def test_capability_closure_cannot_precede_its_actual_observations(identity):
    data, records, subject, digest = evidence_package()
    data, records = rewrite_records(data, records, lambda row: {
        **row, "observed_at": (NOW - timedelta(minutes=1)).isoformat()
    } if row["kind"] == "capability_closure" and row["id"] == identity else None)
    with pytest.raises(ValueError, match="precedes"):
        validate_package(data, records, subject, digest)


@pytest.mark.parametrize("identity", ["gsc-live", "documentation-install-success"])
@pytest.mark.parametrize("mutation", ["wrong-sha", "extra-key"])
def test_known_observation_paths_do_not_bypass_exact_reference_integrity(identity, mutation):
    data, records, subject, digest = evidence_package()

    def malformed_reference(row):
        if row["kind"] != "capability_closure" or row["id"] != identity:
            return None
        first, *rest = row["observations"]
        changed = {**first, **({"sha256": "0" * 64} if mutation == "wrong-sha" else {"approved": True})}
        return {**row, "observations": [changed, *rest]}

    data, records = rewrite_records(data, records, malformed_reference)
    with pytest.raises(ValueError):
        validate_package(data, records, subject, digest)
