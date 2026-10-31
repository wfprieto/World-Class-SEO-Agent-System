"""Synthetic complete benchmark builders; these fixtures never grant release trust."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import publication_policy as policy
from scripts.publication_benchmark import benchmark_policy, validate_benchmark

NOW = datetime(2026, 10, 31, 2, 0, tzinfo=UTC)
CANDIDATE = "a" * 40


def pack_record(records, record):
    raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = f"publication-evidence/records/{digest}.json"
    records[path] = raw
    return {"path": path, "sha256": digest}


def dimensions():
    path = Path(__file__).resolve().parents[1] / "evaluation/comparative/benchmark-cases.json"
    data = json.loads(path.read_text())
    return data["archetypes"], data["tasks"]


def benchmark_package():
    records = {}
    archetypes, tasks = dimensions()
    case_ids = [f"{archetype}/{task}" for archetype in archetypes for task in tasks]
    frozen = (NOW - timedelta(minutes=2)).isoformat()
    corpus = pack_record(records, {
        "kind": "benchmark_corpus", "candidate_commit": CANDIDATE,
        "comparator_commit": policy.COMPARATOR_COMMIT,
        "case_ids": case_ids, "frozen_at": frozen,
    })
    truth = pack_record(records, {
        "kind": "benchmark_ground_truth_manifest", "case_ids": case_ids, "sealed_at": frozen,
    })
    blind = pack_record(records, {
        "kind": "benchmark_blinding_manifest", "case_ids": case_ids,
        "builder_id": "synthetic-builder", "evaluator_id": "synthetic-independent-expert",
        "sealed_at": frozen,
    })
    cases = []
    for archetype in archetypes:
        for task in tasks:
            case_id = f"{archetype}/{task}"
            source = pack_record(records, {
                "kind": "finding_evidence", "case_id": case_id,
                "observation": "Synthetic known-answer observation, not a live site.",
            })
            findings = [{"id": "f1", "severity": "High", "statement": "Synthetic defect",
                         "evidence_refs": [source]}]
            output = {"kind": "benchmark_output", "case_id": case_id,
                      "executed_at": (NOW - timedelta(minutes=1)).isoformat(),
                      "findings": findings, "required_handoffs": ["h1"],
                      "consumed_handoffs": ["h1"]}
            target = pack_record(records, {**output, "system_commit": CANDIDATE})
            comparator = pack_record(records, {**output, "system_commit": policy.COMPARATOR_COMMIT})
            ground_truth = pack_record(records, {
                "kind": "benchmark_ground_truth", "case_id": case_id,
                "findings": [{"id": "truth1", "severity": "High", "evidence_refs": [source]}],
            })
            blinding = pack_record(records, {
                "kind": "benchmark_blinding", "case_id": case_id,
                "evaluator_id": "synthetic-independent-expert", "target_label": "A",
                "comparator_label": "B", "evaluated_without_identity": True,
                "revealed_at": NOW.isoformat(),
            })
            evaluation = pack_record(records, {
                "kind": "benchmark_evaluation", "case_id": case_id,
                "evaluator_id": "synthetic-independent-expert", "evaluated_at": NOW.isoformat(),
                "target_matches": [{"finding_id": "f1", "truth_id": "truth1"}],
                "comparator_matches": [{"finding_id": "f1", "truth_id": "truth1"}],
                "schema_valid": {"target": True, "comparator": True},
                "unsupported_claims": {"target": [], "comparator": []},
                "secret_exposures": {"target": [], "comparator": []},
                "unbounded_paid_calls": {"target": [], "comparator": []},
            })
            cases.append({"archetype": archetype, "task": task, "target": target,
                          "comparator": comparator, "ground_truth": ground_truth,
                          "blinding": blinding, "evaluation": evaluation})
    manifests = {"corpus": corpus, "ground_truth": truth, "blinding": blind}
    for field, reference in manifests.items():
        record = json.loads(records.pop(reference["path"]))
        bindings = {}
        for case in cases:
            case_id = f"{case['archetype']}/{case['task']}"
            if field == "corpus":
                output = json.loads(records[case["target"]["path"]])
                bindings[case_id] = output["findings"][0]["evidence_refs"]
            else:
                bindings[case_id] = case[field]
        manifests[field] = pack_record(records, {**record, "records": bindings})
    return {"candidate_commit": CANDIDATE, "comparator_commit": policy.COMPARATOR_COMMIT,
            **manifests, "cases": cases}, records


def replace_record(package, records, case_field, changes, index=0):
    case = package["cases"][index]
    old = case[case_field]
    record = json.loads(records[old["path"]])
    new = {**record, **changes}
    case[case_field] = pack_record(records, new)
    records.pop(old["path"])


def rewrite_records(value, records, mutate):
    """Reseal synthetic DAGs so negative tests exercise semantics, not stale hashes."""
    rewritten = {}
    cache = {}

    def visit(item):
        if isinstance(item, list):
            return [visit(child) for child in item]
        if not isinstance(item, dict):
            return item
        if set(item) == {"path", "sha256"}:
            path = item["path"]
            if path not in cache:
                record = visit(json.loads(records[path]))
                changed = mutate(record)
                cache[path] = pack_record(rewritten, record if changed is None else changed)
            return cache[path]
        return {key: visit(child) for key, child in item.items()}

    return visit(value), rewritten


def test_complete_raw_105_case_benchmark_recomputes_metrics():
    package, records = benchmark_package()
    result = validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)
    assert result == {
        "cases": 105, "critical_recall": 1.0, "precision": 1.0,
        "schema_valid_rate": 1.0, "handoff_consumption_rate": 1.0,
        "unsupported_claims": 0, "secret_exposures": 0, "unbounded_paid_calls": 0,
    }


@pytest.mark.parametrize("change", ["missing", "duplicate", "status", "threshold", "comparator"])
def test_rejects_incomplete_duplicate_status_only_or_reconfigured_benchmark(change):
    package, records = benchmark_package()
    if change == "missing":
        package["cases"].pop()
    elif change == "duplicate":
        package["cases"][-1] = package["cases"][0]
    elif change == "status":
        package = {"execution_state": "PASS"}
    elif change == "threshold":
        package["gates"] = {"precision_min": 0}
    else:
        package["comparator_commit"] = "c" * 40
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("schema_valid", {"target": False, "comparator": True}),
    ("unsupported_claims", {"target": ["unsupported-fact"], "comparator": []}),
    ("secret_exposures", {"target": ["sanitized-exposure-id"], "comparator": []}),
    ("unbounded_paid_calls", {"target": ["call1"], "comparator": []}),
    ("target_matches", [{"finding_id": "absent", "truth_id": "truth1"}]),
    ("evaluator_id", "synthetic-builder"),
])
def test_rejects_adjudicated_quality_or_matching_failure(field, value):
    package, records = benchmark_package()
    replace_record(package, records, "evaluation", {field: value})
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_raw_record_digest_not_boolean_or_reported_count_is_authority_for_content():
    package, records = benchmark_package()
    reference = package["cases"][0]["target"]
    records[reference["path"]] = b'{"kind":"tampered"}'
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_false_precision_or_recall_cannot_hide_behind_execution_pass():
    package, records = benchmark_package()
    for index in range(6):
        replace_record(package, records, "evaluation", {"target_matches": []}, index)
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_unconsumed_required_handoff_fails_complete_consumption_gate():
    package, records = benchmark_package()
    replace_record(package, records, "target", {"consumed_handoffs": []})
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_ground_truth_cannot_change_without_resealing_the_manifest():
    package, records = benchmark_package()
    old = json.loads(records[package["cases"][0]["ground_truth"]["path"]])
    findings = [{**old["findings"][0], "severity": "Critical"}]
    replace_record(package, records, "ground_truth", {"findings": findings})
    with pytest.raises(ValueError):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_canonical_numeric_thresholds_and_all_dimensions_are_unchanged():
    archetypes, tasks, gates = benchmark_policy()
    assert (len(archetypes), len(tasks)) == (7, 15)
    assert gates == {"critical_recall_min": 0.95, "precision_min": 0.9,
                     "unsupported_claims_max": 0, "schema_valid_rate": 1.0,
                     "handoff_consumption_rate": 1.0, "secret_exposure_max": 0,
                     "unbounded_paid_calls_max": 0}


def test_blinding_reveal_cannot_be_in_the_unobserved_future_even_with_resealed_data():
    package, records = benchmark_package()
    package, records = rewrite_records(package, records, lambda row: {
        **row, "revealed_at": (NOW + timedelta(days=1)).isoformat()
    } if row["kind"] == "benchmark_blinding" else None)
    with pytest.raises(ValueError, match="future"):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_repeating_the_same_finding_evidence_is_not_independent_support():
    package, records = benchmark_package()

    def duplicate(row):
        if row["kind"] == "benchmark_output":
            findings = [{**row["findings"][0], "evidence_refs": row["findings"][0]["evidence_refs"] * 2}]
            return {**row, "findings": findings}
        return None

    package, records = rewrite_records(package, records, duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


@pytest.mark.parametrize("field", ["secret_exposures", "unbounded_paid_calls"])
def test_unsafe_comparator_execution_is_not_excused_as_lower_baseline_quality(field):
    package, records = benchmark_package()
    replace_record(package, records, "evaluation", {field: {"target": [], "comparator": ["unsafe-item"]}})
    with pytest.raises(ValueError, match=field):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_precision_gate_rejects_unmatched_output_findings_despite_perfect_critical_recall():
    package, records = benchmark_package()

    def false_positive(row):
        if row["kind"] == "benchmark_output" and row["system_commit"] == CANDIDATE:
            false_finding = {**row["findings"][0], "id": "false-positive", "severity": "Low"}
            return {**row, "findings": [*row["findings"], false_finding]}
        return None

    package, records = rewrite_records(package, records, false_positive)
    with pytest.raises(ValueError, match="precision"):
        validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)


def test_lower_quality_comparator_unsupported_claims_remain_measured_baseline_flaws():
    package, records = benchmark_package()
    replace_record(package, records, "evaluation", {
        "unsupported_claims": {"target": [], "comparator": ["baseline-unsupported-claim"]}})
    assert validate_benchmark(package, records, candidate_commit=CANDIDATE, now=NOW)["unsupported_claims"] == 0
