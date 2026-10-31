"""Clearly synthetic proof records only; no execution or permission evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_publication_arguments import valid_argv
from test_publication_capability_results import synthetic_bing_success, valid_result

from adapters.mcp_extensions import REGISTRY
from scripts.publication_capability_checks import validate_observation
from scripts.publication_evidence_records import EvidenceRecords
from scripts.publication_prerequisites import closure_prerequisites, job_claims, prerequisites
from scripts.publication_subject import JsonObject
from scripts.publication_targets import scope_digest, target_digest

NOW = datetime(2026, 10, 31, 2, 0, tzinfo=UTC)
DIGEST = "b" * 64
SUBJECT: JsonObject = {"candidate_commit": "a" * 40, "prepared_at": (NOW - timedelta(minutes=5)).isoformat()}


def _pack(records: dict[str, bytes], row: JsonObject) -> JsonObject:
    raw = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = f"publication-evidence/records/{digest}.json"
    records[path] = raw
    return {"path": path, "sha256": digest}


def _input(url: str = "https://example.com/") -> JsonObject:
    content = json.dumps([url])
    return {"kind": "command_input", "candidate_commit": SUBJECT["candidate_commit"],
        "prepared_subject_sha256": DIGEST, "argument_path": "/synthetic/input.json", "format": "urls-json",
        "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}


def prerequisite_record(command: str, platform: str = "ubuntu", job_id: int = 123) -> JsonObject:
    """SYNTHETIC ONLY. No current successful Bing record is available."""
    if command not in {"browser.install", "render.health", "indexnow.validate"}:
        raise ValueError("No successful current-source prerequisite fixture")
    result = ({"installed": True, "binary_sha256": "1" * 64, "browser_version": "SYNTHETIC-Chromium",
        "output_bytes": 1, "stdout_sha256": "2" * 64, "stderr_sha256": "3" * 64}
        if command == "browser.install" else valid_result(command))
    seconds = {"browser.install": 3, "render.health": 2, "indexnow.validate": 1}[command]
    row = {"kind": "capability_prerequisite", "candidate_commit": SUBJECT["candidate_commit"],
        "prepared_subject_sha256": DIGEST, "capability_id": "bing-indexnow" if command == "indexnow.validate" else "render-installable",
        "command_id": command, "platform": platform, "job_id": job_id,
        "executed_at": (NOW - timedelta(seconds=seconds)).isoformat(), "argv": valid_argv(command),
        "exit_code": 0, "result": result}
    if command == "indexnow.validate":
        row["input_file"] = _pack({}, _input())
    return row


def synthetic_bing_prerequisite(platform: str = "ubuntu", job_id: int = 123) -> JsonObject:
    """COUNTERFACTUAL only: source registry DATA must be explicitly scoped/restored."""
    row = prerequisite_record("render.health", platform, job_id)
    row.update({"capability_id": "bing-indexnow", "command_id": "bing.preflight",
                "argv": valid_argv("bing.preflight"), "result": synthetic_bing_success()})
    return row


def _live(records: dict[str, bytes], commands: list[str], platform: str, job: int,
          *, at: datetime = NOW) -> JsonObject:
    target = ({"kind": "indexnow_url_set", "values": ["https://example.com/"]}
              if commands == ["indexnow.submit"] else {"kind": "web_url", "value": "https://example.com/"})
    endpoint = "api.indexnow.org" if commands == ["indexnow.submit"] else "example.com"
    scope = {"targets": [target], "redirect_targets": [], "endpoint_hosts": [endpoint],
             "methods": ["POST" if commands == ["indexnow.submit"] else "GET"]}
    auth = {"target": target, "target_sha256": target_digest(target), "scope": scope,
        "scope_sha256": scope_digest(scope), "starts_at": (NOW - timedelta(minutes=4)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=1)).isoformat()}
    row: JsonObject = {"kind": "live_observation", "candidate_commit": SUBJECT["candidate_commit"],
        "prepared_subject_sha256": DIGEST, "mode": "AUTHORIZED_LIVE", "capabilities": commands,
        "platform": platform, "job_id": job, "observed_at": at.isoformat(),
        "argv": {command: valid_argv(command) for command in commands}, "exit_codes": dict.fromkeys(commands, 0)}
    normalized: JsonObject = {"kind": "normalized_observation", "candidate_commit": SUBJECT["candidate_commit"],
        "prepared_subject_sha256": DIGEST, "capabilities": commands, "observed_at": at.isoformat(),
        "target": target, "target_sha256": target_digest(target), "data": {command: valid_result(command) for command in commands},
        "requests_made": len(commands), "requests": [{"request_id": platform + command, "command_id": command,
            "method": scope["methods"][0], "endpoint_host": endpoint, "target": target, "http_status": 200,
            "occurred_at": (at - timedelta(microseconds=1)).isoformat()} for command in commands]}
    if commands == ["indexnow.submit"]:
        row["input_file"] = _pack(records, _input())
    row["normalized"] = _pack(records, normalized)
    # Store a synthetic authorization only for real pure source validation in _consume.
    row["authorization"] = _pack(records, {"kind": "synthetic_authorization", **auth})
    return _pack(records, row)


def _consume(reader: EvidenceRecords, references: list[JsonObject]) -> None:
    for reference in references:
        row = reader.values[str(reference["path"])]
        reader.read(reference, kind=str(row["kind"]), keys=set(row) - {"kind"})
        normalized_ref = row["normalized"]
        normalized = reader.values[reader.reference_path(normalized_ref)]
        reader.read(normalized_ref, kind="normalized_observation", keys=set(normalized) - {"kind"})
        authorization = reader.values[reader.reference_path(row["authorization"])]
        validate_observation(row, normalized, authorization, reader, SUBJECT, NOW)


def _render_package() -> tuple[dict[str, bytes], list[JsonObject], list[JsonObject]]:
    records: dict[str, bytes] = {}
    local, remote = [], []
    for platform, job in (("ubuntu", 123), ("windows", 456)):
        for command in ("browser.install", "render.health"):
            local.append(_pack(records, prerequisite_record(command, platform, job)))
        remote.append(_live(records, ["render.page", "render.screenshot"], platform, job))
    return records, local, remote


def _bing_package() -> tuple[dict[str, bytes], list[JsonObject], list[JsonObject]]:
    records: dict[str, bytes] = {}
    _pack(records, _input())
    local = [_pack(records, synthetic_bing_prerequisite()),
             _pack(records, prerequisite_record("indexnow.validate", "windows", 456))]
    remote = [_live(records, ["indexnow.submit"], "ubuntu", 789)]
    return records, local, remote


def _reader(records: dict[str, bytes], local: list[JsonObject], remote: list[JsonObject]) -> EvidenceRecords:
    reader = EvidenceRecords(records)
    prerequisites(local, reader, SUBJECT, DIGEST, NOW)
    _consume(reader, remote)
    return reader


def _paths(*groups: list[JsonObject]) -> list[str]:
    return [str(reference["path"]) for group in groups for reference in group]


def _section(local: list[JsonObject], remote: list[JsonObject]) -> JsonObject:
    return {"candidate_commit": SUBJECT["candidate_commit"], "prepared_subject_sha256": DIGEST,
            "mode": "AUTHORIZED_LIVE", "observations": remote, "prerequisites": local}


def test_marker_only_install_is_not_a_typed_successful_prerequisite() -> None:
    records: dict[str, bytes] = {}
    row = prerequisite_record("browser.install")
    row["result"] = {"installed": True}
    reference = _pack(records, row)
    with pytest.raises(ValueError):
        prerequisites([reference], EvidenceRecords(records), SUBJECT, DIGEST, NOW)


@pytest.mark.parametrize("command", ["browser.install", "render.health", "indexnow.validate"])
def test_current_typed_prerequisites_reuse_actual_source_validators(command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Prerequisite validation attempted DNS, HTTP or an argv file open")

    for operation in ("socket.getaddrinfo", "urllib.request.urlopen", "pathlib.Path.open"):
        monkeypatch.setattr(operation, forbidden)
    records: dict[str, bytes] = {}
    _pack(records, _input())
    reference = _pack(records, prerequisite_record(command))
    reader = EvidenceRecords(records)
    assert prerequisites([reference], reader, SUBJECT, DIGEST, NOW) == {reference["path"]: {command}}
    assert reference["path"] in reader.used


def test_complete_two_platform_install_health_and_real_typed_smoke_closure() -> None:
    records, local, remote = _render_package()
    reader = _reader(records, local, remote)
    closure_prerequisites("render-installable", _paths(local, remote), reader, SUBJECT, NOW)
    claims = job_claims(_section(local, remote), reader)
    assert len(claims) == 10  # two observations + four requests + four local events
    assert {row["platform"] for row in claims} == {"ubuntu", "windows"}
    assert {row["job_id"] for row in claims} == {123, 456}


def test_current_bing_is_blocked_and_no_default_success_fixture_exists() -> None:
    with pytest.raises(ValueError):
        prerequisite_record("bing.preflight")
    records, local, _remote = _bing_package()
    with pytest.raises(ValueError):
        prerequisites(local, EvidenceRecords(records), SUBJECT, DIGEST, NOW)


def test_counterfactual_bing_cross_job_platform_grammar_is_not_current_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    original = REGISTRY["bing-webmaster"]
    with monkeypatch.context() as scoped:
        scoped.setitem(REGISTRY, "bing-webmaster", replace(original, live_state="CONFIGURABLE"))
        records, local, remote = _bing_package()
        reader = _reader(records, local, remote)
        closure_prerequisites("bing-indexnow", _paths(local, remote), reader, SUBJECT, NOW)
    assert REGISTRY["bing-webmaster"] == original
    with pytest.raises(ValueError):
        closure_prerequisites("bing-indexnow", _paths(local, remote), reader, SUBJECT, NOW)


@pytest.mark.parametrize(("field", "value"), [("exit_code", True), ("exit_code", 1), ("exit_code", "0"),
    ("job_id", True), ("job_id", 0), ("platform", "linux"), ("command_id", "render.page"),
    ("capability_id", "different"), ("candidate_commit", "f" * 40), ("prepared_subject_sha256", "f" * 64),
    ("kind", "other"), ("executed_at", (NOW - timedelta(minutes=6)).isoformat()),
    ("executed_at", (NOW + timedelta(minutes=10)).isoformat()), ("argv", ["sh", "-c", "anything"]),
    ("result", {"installed": True}), ("unknown", "forbidden")])
def test_strict_common_prerequisite_metadata_schema_and_freshness(field: str, value: object) -> None:
    row = prerequisite_record("browser.install")
    row[field] = value
    records: dict[str, bytes] = {}
    reference = _pack(records, row)
    with pytest.raises(ValueError):
        prerequisites([reference], EvidenceRecords(records), SUBJECT, DIGEST, NOW)


@pytest.mark.parametrize(("field", "value"), [("installed", 1), ("binary_sha256", "not-sha"),
    ("browser_version", ""), ("output_bytes", True), ("output_bytes", 0), ("stdout_sha256", "f" * 63),
    ("stderr_sha256", None), ("unknown", True)])
def test_install_exact_result_not_an_installed_marker(field: str, value: object) -> None:
    row = prerequisite_record("browser.install")
    row["result"][field] = value
    records: dict[str, bytes] = {}
    reference = _pack(records, row)
    with pytest.raises(ValueError):
        prerequisites([reference], EvidenceRecords(records), SUBJECT, DIGEST, NOW)


def test_duplicate_and_missing_reference_or_wrong_reference_digest_fails() -> None:
    records: dict[str, bytes] = {}
    ref = _pack(records, prerequisite_record("browser.install"))
    for references in ([ref, ref], [{**ref, "sha256": "0" * 64}], [{**ref, "unknown": 1}], [{}]):
        with pytest.raises(ValueError):
            prerequisites(references, EvidenceRecords(records), SUBJECT, DIGEST, NOW)
    assert prerequisites([], EvidenceRecords({}), SUBJECT, DIGEST, NOW) == {}


@pytest.mark.parametrize("omit", range(6))
def test_missing_either_platform_install_health_or_smokes_cannot_close(omit: int) -> None:
    records, local, remote = _render_package()
    reader = _reader(records, local, remote)
    paths = _paths(local, remote)
    del paths[omit]
    with pytest.raises(ValueError):
        closure_prerequisites("render-installable", paths, reader, SUBJECT, NOW)


def _rewrite_render_rows(change: str, records: dict[str, bytes], local: list[JsonObject], remote: list[JsonObject]) -> None:
    if change in {"health-job", "late-install", "late-health", "duplicate-local", "different-subject"}:
        index = 0 if change == "late-install" else 1
        row = json.loads(records[str(local[index]["path"])])
        if change == "health-job":
            row["job_id"] = 999
        elif change == "different-subject":
            row["prepared_subject_sha256"] = "c" * 64
        else:
            row["executed_at"] = NOW.isoformat() if change == "late-install" else (NOW + timedelta(seconds=1)).isoformat()
        replacement = _pack(records, row)
        if change == "duplicate-local":
            local.append(replacement)
        else:
            local[index] = replacement
    if change == "same-os-jobs":
        for ref in local[2:] + remote[1:]:
            row = json.loads(records[str(ref["path"])])
            row["job_id"] = 123
            replacement = _pack(records, row)
            if ref in local:
                local[local.index(ref)] = replacement
            else:
                remote[remote.index(ref)] = replacement


def _mutate_consumed_render(change: str, reader: EvidenceRecords, local: list[JsonObject], remote: list[JsonObject]) -> None:
    if change == "unconsumed":
        reader.used.remove(str(local[0]["path"]))
    elif change == "raw-marker":
        reader.values[str(local[0]["path"])]["result"] = {"installed": True}
    elif change in {"live-marker", "foreign-normalized"}:
        normal = reader.values[reader.reference_path(reader.values[str(remote[0]["path"])]["normalized"])]
        if change == "live-marker":
            normal["data"] = {"render.page": {"status": "ok"}, "render.screenshot": {"status": "ok"}}
        else:
            normal["candidate_commit"] = "f" * 40
    elif change == "unknown-row":
        reader.values[str(local[0]["path"])]["kind"] = "community_observation"


@pytest.mark.parametrize("change", ["health-job", "same-os-jobs", "late-install", "late-health", "duplicate-local",
    "unconsumed", "raw-marker", "live-marker", "foreign-normalized", "unknown-row", "different-subject"])
def test_joint_render_context_ordering_typed_data_and_reader_identity(change: str) -> None:
    records, local, remote = _render_package()
    _rewrite_render_rows(change, records, local, remote)
    reader = EvidenceRecords(records)
    if change != "different-subject":
        prerequisites(local, reader, SUBJECT, DIGEST, NOW)
    else:
        for ref in local:
            row = reader.values[str(ref["path"])]
            prerequisites([ref], reader, SUBJECT, str(row["prepared_subject_sha256"]), NOW)
    _consume(reader, remote)
    _mutate_consumed_render(change, reader, local, remote)
    with pytest.raises(ValueError):
        closure_prerequisites("render-installable", _paths(local, remote), reader, SUBJECT, NOW)


@pytest.mark.parametrize("change", ["foreign-source", "foreign-subject", "missing-bound", "wrong-mode"])
def test_job_claims_cannot_be_reassigned_to_a_foreign_live_section(change: str) -> None:
    records, local, remote = _render_package()
    reader = _reader(records, local, remote)
    section = _section(local, remote)
    if change == "foreign-source":
        section["candidate_commit"] = "f" * 40
    elif change == "foreign-subject":
        section["prepared_subject_sha256"] = "f" * 64
    elif change == "wrong-mode":
        section["mode"] = "FIXTURE"
    else:
        del section["candidate_commit"]
    with pytest.raises(ValueError):
        job_claims(section, reader)


@pytest.mark.parametrize("change", ["argument-path", "content-digest", "format", "wrong-input-subject",
    "missing-input", "result-url-swap", "url-count", "extra-input-on-health"])
def test_indexnow_input_is_bound_bytes_not_a_trusted_path_or_self_digest(change: str) -> None:
    records: dict[str, bytes] = {}
    source = _input()
    row = prerequisite_record("indexnow.validate")
    if change == "argument-path":
        source["argument_path"] = "/different/input.json"
    elif change == "content-digest":
        source["content"] = '["https://example.com/other"]'
    elif change == "format":
        source["format"] = "urls-text"
    elif change == "wrong-input-subject":
        source["prepared_subject_sha256"] = "f" * 64
    elif change == "result-url-swap":
        row["result"]["data"]["urls"] = ["https://example.com/other"]
    elif change == "url-count":
        row["result"]["data"]["url_count"] = 2
    row["input_file"] = _pack(records, source)
    if change == "missing-input":
        del row["input_file"]
    elif change == "extra-input-on-health":
        row = {**prerequisite_record("render.health"), "input_file": row["input_file"]}
    ref = _pack(records, row)
    with pytest.raises(ValueError):
        prerequisites([ref], EvidenceRecords(records), SUBJECT, DIGEST, NOW)


@pytest.mark.parametrize("change", ["preflight-after", "validate-after", "missing-preflight", "missing-validate", "missing-submit", "url-set-swap"])
def test_counterfactual_bing_requires_actual_checks_before_matching_submission(change: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = REGISTRY["bing-webmaster"]
    with monkeypatch.context() as scoped:
        scoped.setitem(REGISTRY, "bing-webmaster", replace(original, live_state="CONFIGURABLE"))
        records, local, remote = _bing_package()
        if change in {"preflight-after", "validate-after", "url-set-swap"}:
            index = 0 if change == "preflight-after" else 1
            row = json.loads(records[str(local[index]["path"])])
            if change == "url-set-swap":
                row["input_file"] = _pack(records, _input("https://example.com/other"))
                row["result"]["data"]["urls"] = ["https://example.com/other"]
            else:
                row["executed_at"] = (NOW + timedelta(seconds=1)).isoformat()
            local[index] = _pack(records, row)
        reader = _reader(records, local, remote)
        paths = _paths(local, remote)
        if change.startswith("missing-"):
            del paths[{"missing-preflight": 0, "missing-validate": 1, "missing-submit": 2}[change]]
        with pytest.raises(ValueError):
            closure_prerequisites("bing-indexnow", paths, reader, SUBJECT, NOW)
    assert REGISTRY["bing-webmaster"] == original


@pytest.mark.parametrize("change", ["duplicate-ref", "not-consumed", "normalized-not-consumed", "bool-job", "unknown-platform", "marker-result", "missing-request-time", "same-job-both-os"])
def test_job_claims_only_extracts_typed_validated_direct_events(change: str) -> None:
    records, local, remote = _render_package()
    reader = _reader(records, local, remote)
    section = _section(local, remote)
    observation = reader.values[str(remote[0]["path"])]
    normalized_path = reader.reference_path(observation["normalized"])
    if change == "duplicate-ref":
        section["observations"] = [remote[0], remote[0]]
    elif change == "not-consumed":
        reader.used.remove(str(local[0]["path"]))
    elif change == "normalized-not-consumed":
        reader.used.remove(normalized_path)
    elif change == "bool-job":
        observation["job_id"] = True
    elif change == "unknown-platform":
        observation["platform"] = "linux"
    elif change == "marker-result":
        reader.values[str(local[0]["path"])]["result"] = {"installed": True}
    elif change == "missing-request-time":
        del reader.values[normalized_path]["requests"][0]["occurred_at"]
    else:
        reader.values[str(remote[1]["path"])]["job_id"] = 123
    with pytest.raises(ValueError):
        job_claims(section, reader)


def test_request_claims_inherit_parent_job_and_never_recurse_unrelated_records() -> None:
    records, local, remote = _render_package()
    reader = _reader(records, local, remote)
    observation = reader.values[str(remote[0]["path"])]
    normalized = reader.values[reader.reference_path(observation["normalized"])]
    normalized["community"] = {"job_id": 999, "platform": "unrelated", "executed_at": "invalid"}
    normalized["requests"][0]["job_id"] = 999
    claims = job_claims(_section(local, remote), reader)
    assert len(claims) == 10
    assert all(row["job_id"] != 999 for row in claims)
