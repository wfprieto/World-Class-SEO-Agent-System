"""Recompute a complete measured benchmark without asserting producer authority.

The exact benchmark object has candidate_commit/comparator_commit/corpus/
ground_truth/blinding/cases. Global manifest records freeze all case IDs and the
independent evaluator. Each of the105 cases names target/comparator output,
ground-truth, blinding and evaluation records. Outputs contain normalized findings
(id/severity/statement/evidence_refs), required/consumed handoffs and execution
times. Truth findings carry id/severity/evidence_refs. Evaluation records contain
one-to-one finding/truth matches, evaluator/time and per-system adjudicated
schema_valid, unsupported_claims, secret_exposures and unbounded_paid_calls.
Blinding records bind labels, evaluator, hidden-identity boolean and reveal time.
None of these self-contained semantic checks authenticate the execution origin.
Quality thresholds apply to the target; secret exposure and unbounded paid calls
are run-level safety totals across BOTH systems. Baseline unsupported claims may
remain comparative flaws, not permission to expose secrets or exceed spend scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_evidence_records import EvidenceRecords, object_list, string_list
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    json_object,
    object_value,
    require_fresh,
    string_value,
)

ROOT = Path(__file__).resolve().parents[1]
SEVERITIES = {"Critical", "High", "Medium", "Low"}


def benchmark_policy() -> tuple[list[str], list[str], JsonObject]:
    """Load the sole threshold/dimension authority from trusted source, never E."""
    data = json_object((ROOT / "evaluation/comparative/benchmark-cases.json").read_bytes(),
                       "benchmark policy")
    exact_keys(data, {"schema_version", "archetypes", "tasks", "gates", "execution_state",
                      "reason"}, "benchmark policy")
    archetypes = string_list(data["archetypes"], "archetypes", nonempty=True)
    tasks = string_list(data["tasks"], "tasks", nonempty=True)
    if data["schema_version"] != "1.0.0" or len(archetypes) != 7 or len(tasks) != 15:
        raise ValueError("benchmark policy must cover the canonical seven-by-fifteen scope")
    gates = object_value(data["gates"], "benchmark gates")
    exact_keys(gates, {"critical_recall_min", "precision_min", "unsupported_claims_max",
                       "schema_valid_rate", "handoff_consumption_rate", "secret_exposure_max",
                       "unbounded_paid_calls_max"}, "benchmark gates")
    for value in gates.values():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 1:
            raise ValueError("benchmark thresholds must be finite bounded numeric values")
    return archetypes, tasks, gates


def _manifest(
    value: JsonObject, reader: EvidenceRecords, case_ids: set[str], candidate: str, now: datetime,
) -> tuple[datetime, str, dict[str, JsonObject]]:
    corpus = reader.read(value["corpus"], kind="benchmark_corpus", keys={
        "candidate_commit", "comparator_commit", "case_ids", "frozen_at", "records"})
    if corpus["candidate_commit"] != candidate or corpus["comparator_commit"] != policy.COMPARATOR_COMMIT:
        raise ValueError("benchmark corpus source mismatch")
    truth = reader.read(value["ground_truth"], kind="benchmark_ground_truth_manifest",
                        keys={"case_ids", "sealed_at", "records"})
    blind = reader.read(value["blinding"], kind="benchmark_blinding_manifest", keys={
        "case_ids", "builder_id", "evaluator_id", "sealed_at", "records"})
    bindings = {}
    for field, record in (("corpus", corpus), ("ground_truth", truth), ("blinding", blind)):
        bindings[field] = object_value(record["records"], "sealed case records")
        if set(bindings[field]) != case_ids:
            raise ValueError("sealed benchmark records do not cover the exact case set")
    for record in (corpus, truth, blind):
        if set(string_list(record["case_ids"], "manifest case IDs")) != case_ids:
            raise ValueError("benchmark manifest scope is incomplete")
    if string_value(blind["builder_id"], "builder") == string_value(blind["evaluator_id"], "evaluator"):
        raise ValueError("benchmark evaluator must be distinct from builder")
    times = [require_fresh(record[field], now=now, ttl=policy.EVIDENCE_TTL_SECONDS, label=field)
             for record, field in ((corpus, "frozen_at"), (truth, "sealed_at"), (blind, "sealed_at"))]
    return max(times), string_value(blind["evaluator_id"], "evaluator"), bindings


def _findings(
    value: object, reader: EvidenceRecords, case_id: str, inputs: set[str], *, output: bool,
) -> dict[str, str]:
    findings: dict[str, str] = {}
    for row in object_list(value, "findings", nonempty=False):
        keys = {"id", "severity", "evidence_refs"} | ({"statement"} if output else set())
        exact_keys(row, keys, "finding")
        identity = string_value(row["id"], "finding ID")
        severity = string_value(row["severity"], "finding severity")
        if identity in findings or severity not in SEVERITIES:
            raise ValueError("duplicate finding or invalid severity")
        if output:
            string_value(row["statement"], "finding statement")
        cited: set[str] = set()
        for reference in object_list(row["evidence_refs"], "finding source refs"):
            path = string_value(reference.get("path"), "finding evidence path")
            if path in cited:
                raise ValueError("duplicate finding evidence reference")
            if path not in inputs:
                raise ValueError("finding source was not frozen in the corpus manifest")
            cited.add(path)
            source = reader.read(reference, kind="finding_evidence", keys={"case_id", "observation"})
            if source["case_id"] != case_id:
                raise ValueError("finding evidence belongs to another case")
            string_value(source["observation"], "finding observation")
        findings[identity] = severity
    return findings


def _matches(value: object, findings: dict[str, str], truth: dict[str, str]) -> set[str]:
    matched_findings: set[str] = set()
    matched_truth: set[str] = set()
    for row in object_list(value, "adjudicated matches", nonempty=False):
        exact_keys(row, {"finding_id", "truth_id"}, "adjudicated match")
        finding = string_value(row["finding_id"], "matched finding")
        expected = string_value(row["truth_id"], "matched truth")
        if finding not in findings or expected not in truth:
            raise ValueError("adjudicated match refers to absent raw finding or truth")
        if finding in matched_findings or expected in matched_truth:
            raise ValueError("adjudicated matching must be one-to-one")
        matched_findings.add(finding)
        matched_truth.add(expected)
    return matched_truth


def _output(
    reference: object, reader: EvidenceRecords, case_id: str, commit: str, frozen: datetime,
    inputs: set[str], now: datetime,
) -> tuple[dict[str, str], set[str], set[str], datetime]:
    data = reader.read(reference, kind="benchmark_output", keys={"case_id", "system_commit",
                       "executed_at", "findings", "required_handoffs", "consumed_handoffs"})
    if data["case_id"] != case_id or data["system_commit"] != commit:
        raise ValueError("benchmark output source/case mismatch")
    executed = require_fresh(data["executed_at"], now=now, ttl=policy.EVIDENCE_TTL_SECONDS,
                             label="benchmark execution")
    if executed < frozen:
        raise ValueError("benchmark output predates sealed corpus/truth/blinding")
    required = set(string_list(data["required_handoffs"], "required handoffs"))
    consumed = set(string_list(data["consumed_handoffs"], "consumed handoffs"))
    if not consumed.issubset(required):
        raise ValueError("consumed handoff has no required raw counterpart")
    return _findings(data["findings"], reader, case_id, inputs, output=True), required, consumed, executed


def _evaluation_outcomes(evaluation: JsonObject) -> dict[str, int]:
    schema = object_value(evaluation["schema_valid"], "schema results")
    exact_keys(schema, {"target", "comparator"}, "schema results")
    if any(not isinstance(item, bool) for item in schema.values()):
        raise ValueError("schema adjudications must be booleans")
    result = {"schema_valid": int(schema["target"] is True)}
    for field in ("unsupported_claims", "secret_exposures", "unbounded_paid_calls"):
        values = object_value(evaluation[field], field)
        exact_keys(values, {"target", "comparator"}, field)
        result[field] = len(string_list(values["target"], field))
        comparator = string_list(values["comparator"], field)
        if field in {"secret_exposures", "unbounded_paid_calls"}:
            result[field] += len(comparator)
    return result


def _sealed_inputs(reader: EvidenceRecords, value: object, case_id: str) -> set[str]:
    inputs: set[str] = set()
    for reference in object_list(value, "sealed inputs"):
        record = reader.read(reference, kind="finding_evidence", keys={"case_id", "observation"})
        path = string_value(reference["path"], "sealed input path")
        if path in inputs or record["case_id"] != case_id:
            raise ValueError("sealed inputs contain a duplicate or foreign case")
        string_value(record["observation"], "sealed observation")
        inputs.add(path)
    return inputs


def _case(
    row: JsonObject, reader: EvidenceRecords, candidate: str, frozen: datetime, evaluator: str,
    bindings: dict[str, JsonObject], now: datetime,
) -> dict[str, int]:
    case_id = f"{row['archetype']}/{row['task']}"
    for field in ("ground_truth", "blinding"):
        if row[field] != bindings[field][case_id]:
            raise ValueError("case ground truth or blinding differs from its sealed manifest")
    inputs = _sealed_inputs(reader, bindings["corpus"][case_id], case_id)
    target, required, consumed, target_time = _output(
        row["target"], reader, case_id, candidate, frozen, inputs, now)
    comparator, _, _, comparator_time = _output(
        row["comparator"], reader, case_id, policy.COMPARATOR_COMMIT, frozen, inputs, now)
    truth_record = reader.read(row["ground_truth"], kind="benchmark_ground_truth",
                               keys={"case_id", "findings"})
    blind = reader.read(row["blinding"], kind="benchmark_blinding", keys={"case_id",
        "evaluator_id", "target_label", "comparator_label", "evaluated_without_identity", "revealed_at"})
    evaluation = reader.read(row["evaluation"], kind="benchmark_evaluation", keys={"case_id",
        "evaluator_id", "evaluated_at", "target_matches", "comparator_matches", "schema_valid",
        "unsupported_claims", "secret_exposures", "unbounded_paid_calls"})
    if any(record["case_id"] != case_id for record in (truth_record, blind, evaluation)):
        raise ValueError("case record belongs to another benchmark case")
    if blind["evaluator_id"] != evaluator or evaluation["evaluator_id"] != evaluator:
        raise ValueError("benchmark evaluator identity mismatch")
    if (blind["evaluated_without_identity"] is not True
            or string_value(blind["target_label"], "target label")
            == string_value(blind["comparator_label"], "comparator label")):
        raise ValueError("benchmark was not independently blinded")
    evaluated = require_fresh(evaluation["evaluated_at"], now=now,
                              ttl=policy.EVIDENCE_TTL_SECONDS, label="benchmark evaluation")
    revealed = require_fresh(blind["revealed_at"], now=now, ttl=policy.EVIDENCE_TTL_SECONDS,
                             label="blinding reveal")
    if evaluated < max(target_time, comparator_time) or revealed < evaluated:
        raise ValueError("benchmark evaluation/reveal chronology is invalid")
    truth = _findings(truth_record["findings"], reader, case_id, inputs, output=False)
    matched = _matches(evaluation["target_matches"], target, truth)
    _matches(evaluation["comparator_matches"], comparator, truth)
    critical = {key for key, severity in truth.items() if severity in {"Critical", "High"}}
    return {"tp": len(matched), "predicted": len(target), "critical_found": len(critical & matched),
            "critical_total": len(critical), "required": len(required), "consumed": len(consumed),
            **_evaluation_outcomes(evaluation)}


def _metrics(totals: dict[str, int], cases: int, gates: JsonObject) -> JsonObject:
    if not all(totals[key] > 0 for key in ("predicted", "critical_total", "required")):
        raise ValueError("benchmark metric denominators must be nonempty")
    ratios = {
        "critical_recall": Fraction(totals["critical_found"], totals["critical_total"]),
        "precision": Fraction(totals["tp"], totals["predicted"]),
        "schema_valid_rate": Fraction(totals["schema_valid"], cases),
        "handoff_consumption_rate": Fraction(totals["consumed"], totals["required"]),
    }
    for metric, threshold in (("critical_recall", "critical_recall_min"),
                              ("precision", "precision_min"), ("schema_valid_rate", "schema_valid_rate"),
                              ("handoff_consumption_rate", "handoff_consumption_rate")):
        if ratios[metric] < Fraction(str(gates[threshold])):
            raise ValueError(f"measured benchmark {metric} is below its canonical threshold")
    for metric, threshold in (("unsupported_claims", "unsupported_claims_max"),
                              ("secret_exposures", "secret_exposure_max"),
                              ("unbounded_paid_calls", "unbounded_paid_calls_max")):
        if totals[metric] > Fraction(str(gates[threshold])):
            raise ValueError(f"measured benchmark {metric} exceeds its canonical threshold")
    return {"cases": cases, **{key: float(value) for key, value in ratios.items()},
            **{key: totals[key] for key in ("unsupported_claims", "secret_exposures", "unbounded_paid_calls")}}


def benchmark_metrics(
    value: object, reader: EvidenceRecords, *, candidate_commit: str, now: datetime,
) -> JsonObject:
    data = object_value(value, "benchmark")
    exact_keys(data, {"candidate_commit", "comparator_commit", "corpus", "ground_truth",
                      "blinding", "cases"}, "benchmark")
    if data["candidate_commit"] != candidate_commit or data["comparator_commit"] != policy.COMPARATOR_COMMIT:
        raise ValueError("benchmark candidate/comparator mismatch")
    archetypes, tasks, gates = benchmark_policy()
    expected = {f"{archetype}/{task}" for archetype in archetypes for task in tasks}
    frozen, evaluator, bindings = _manifest(data, reader, expected, candidate_commit, now)
    seen: set[str] = set()
    totals: dict[str, int] = {}
    for row in object_list(data["cases"], "benchmark cases"):
        exact_keys(row, {"archetype", "task", "target", "comparator", "ground_truth",
                         "blinding", "evaluation"}, "benchmark case")
        identity = f"{row['archetype']}/{row['task']}"
        if identity not in expected or identity in seen:
            raise ValueError("duplicate or unexpected benchmark case")
        seen.add(identity)
        for key, number in _case(row, reader, candidate_commit, frozen, evaluator, bindings, now).items():
            totals[key] = totals.get(key, 0) + number
    if seen != expected:
        raise ValueError("benchmark must execute all105 canonical archetype/task combinations")
    return _metrics(totals, len(seen), gates)


def validate_benchmark(
    value: object, records: Mapping[str, bytes], *, candidate_commit: str, now: datetime,
) -> JsonObject:
    reader = EvidenceRecords(records)
    result = benchmark_metrics(value, reader, candidate_commit=candidate_commit, now=now)
    reader.finish()
    return result
