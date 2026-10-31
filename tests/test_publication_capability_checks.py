"""Synthetic bound records only, never live calls or an execution authority."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from scripts.publication_capability_checks import validate_observation
from scripts.publication_evidence_records import EvidenceRecords
from scripts.publication_targets import (
    normalize_scope,
    normalize_target,
    scope_digest,
    target_digest,
)
from tests.test_publication_arguments import valid_argv
from tests.test_publication_capability_results import valid_result

NOW = datetime(2026, 10, 31, 4, 0, tzinfo=UTC)
SUBJECT = {"candidate_commit": "a" * 40, "prepared_at": "2026-10-31T03:00:00Z"}
COMMAND_TARGET = {
    "google.gsc-query": ("gsc_property", "sc-domain:example.com", "www.googleapis.com", "POST"),
    "google.gsc-aggregate": ("gsc_property", "sc-domain:example.com", "www.googleapis.com", "POST"),
    "google.ga4-report": ("ga4_property", "properties/123", "analyticsdata.googleapis.com", "POST"),
    "render.page": ("web_url", "https://example.com/", "example.com", "GET"),
    "render.screenshot": ("web_url", "https://example.com/", "example.com", "GET"),
    "links.commoncrawl": ("domain", "example.com", "index.commoncrawl.org", "GET"),
    "domain.history": ("domain", "example.com", "rdap.verisign.com", "GET"),
    "media.youtube-search": ("youtube_query", "SYNTHETIC query", "www.googleapis.com", "GET"),
    "indexnow.submit": ("indexnow_url_set", ["https://example.com/a"], "api.indexnow.org", "POST"),
}


def packet(command: str = "render.page") -> tuple[dict, dict, dict, EvidenceRecords]:
    kind, value, host, method = COMMAND_TARGET[command]
    target = normalize_target({"kind": kind, "values" if kind == "indexnow_url_set" else "value": value})
    scope = normalize_scope({"targets": [target], "redirect_targets": [], "methods": [method], "endpoint_hosts": [host]})
    observation = {"capabilities": [command], "argv": {command: valid_argv(command)},
                   "exit_codes": {command: 0}, "platform": "ubuntu", "job_id": 123,
                   "observed_at": "2026-10-31T03:20:00Z", "prepared_subject_sha256": "b" * 64}
    authorization = {"target": target, "scope": scope, "target_sha256": target_digest(target),
                     "scope_sha256": scope_digest(scope), "starts_at": "2026-10-31T03:05:00Z",
                     "expires_at": "2026-10-31T03:25:00Z"}
    result = valid_result(command)
    count = result["data"].get("request_count", 1)
    if command == "indexnow.submit":
        count = result["data"]["attempts"]
    normalized = {"target": target, "target_sha256": target_digest(target), "data": {command: result},
                  "requests_made": 1, "requests": [{"request_id": "actual-1", "command_id": command,
                    "method": method, "endpoint_host": host, "target": target, "http_status": 200,
                    "occurred_at": "2026-10-31T03:15:00Z"}]}
    if count > 1:
        normalized["requests"] = [{**normalized["requests"][0], "request_id": f"actual-{index}"} for index in range(count)]
        normalized["requests_made"] = count
    if command == "domain.history":
        normalized["requests"][0]["endpoint_host"] = "data.iana.org"
        authorization["scope"]["endpoint_hosts"].append("data.iana.org")
        authorization["scope_sha256"] = scope_digest(authorization["scope"])
    records = {}
    if command == "indexnow.submit":
        content = '["https://example.com/a"]'
        capture = {"kind": "command_input", "candidate_commit": "a" * 40,
                   "prepared_subject_sha256": "b" * 64, "argument_path": "/synthetic/input.json",
                   "format": "urls-json", "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
        raw = json.dumps(capture, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = f"publication-evidence/records/{digest}.json"
        records[path] = raw
        observation["input_file"] = {"path": path, "sha256": digest}
    return observation, normalized, authorization, EvidenceRecords(records)


def validate(parts: tuple) -> None:
    validate_observation(*parts, SUBJECT, NOW)


@pytest.mark.parametrize("command", list(COMMAND_TARGET))
def test_source_typed_concrete_observation(command: str) -> None:
    validate(packet(command))


@pytest.mark.parametrize("command", list(COMMAND_TARGET))
def test_same_opaque_hash_never_authorizes_a_different_concrete_target(command: str) -> None:
    parts = packet(command)
    target = deepcopy(parts[2]["target"])
    if "values" in target:
        target["values"] = ["https://other.example.com/a"]
    elif target["kind"] == "ga4_property":
        target["value"] = "properties/456"
    elif target["kind"] == "youtube_query":
        target["value"] = "DIFFERENT query"
    else:
        target["value"] = str(target["value"]).replace("example.com", "other.example.com")
    parts[2]["target"] = target
    with pytest.raises(ValueError):
        validate(parts)


@pytest.mark.parametrize("command", ["links.commoncrawl", "domain.history", "media.youtube-search", "indexnow.submit"])
def test_result_telemetry_cannot_claim_unobserved_network_requests(command: str) -> None:
    parts = packet(command)
    field = "attempts" if command == "indexnow.submit" else "request_count"
    parts[1]["data"][command]["data"][field] += 1
    if command == "media.youtube-search":
        parts[1]["data"][command]["data"]["quota_units_estimated"] += 1
    with pytest.raises(ValueError):
        validate(parts)


def _change_request(change: str, normalized: dict) -> None:
    request = normalized["requests"][0]
    values = {"request_target": ("target", {"kind": "web_url", "value": "https://other.example.com/"}),
              "method": ("method", "POST"), "endpoint": ("endpoint_host", "other.example.com"),
              "bool_http": ("http_status", True), "unknown_command": ("command_id", "not.executed")}
    times = {"before_grant": "2026-10-31T03:04:59Z", "before_preparation": "2026-10-31T02:59:59Z",
             "after_observation": "2026-10-31T03:20:01Z", "at_expiry": "2026-10-31T03:25:00Z"}
    if change in values:
        field, value = values[change]
        request[field] = value
    elif change in times:
        request["occurred_at"] = times[change]
    else:
        assert change == "duplicate"
        normalized["requests"].append(deepcopy(request))
        normalized["requests_made"] = 2


@pytest.mark.parametrize("change", ["exit", "error", "extra_command", "request_target", "method",
    "endpoint", "duplicate", "bool_http", "unknown_command", "before_grant", "before_preparation",
    "after_observation", "at_expiry", "missing_input", "unapproved_redirect"])
def test_misbound_success_and_hidden_requests_fail_closed(change: str) -> None:
    parts = packet("indexnow.submit" if change == "missing_input" else "render.page")
    observation, normalized, _authorization, _reader = parts
    if change == "exit":
        observation["exit_codes"]["render.page"] = True
    elif change == "error":
        normalized["data"]["render.page"]["data"] = {"error": "denied"}
    elif change == "extra_command":
        normalized["data"]["unknown"] = {}
    elif change == "missing_input":
        del observation["input_file"]
    elif change == "unapproved_redirect":
        normalized["data"]["render.page"]["data"]["final_url"] = "https://other.example.com/"
    else:
        _change_request(change, normalized)
    with pytest.raises(ValueError):
        validate(parts)
