"""Concrete command/result/request/grant checks; data never authorizes execution."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from scripts import publication_policy as policy
from scripts.publication_arguments import command_options
from scripts.publication_capability_results import validate_result
from scripts.publication_evidence_records import (
    EvidenceRecords,
    object_list,
    observed_time,
    string_list,
)
from scripts.publication_input import INPUT_KEYS, captured_urls
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    instant,
    integer_value,
    object_value,
    string_value,
)
from scripts.publication_targets import (
    normalize_host,
    normalize_scope,
    normalize_target,
    scope_digest,
    target_digest,
)

FIELDS = {
    "google.gsc-query": ("gsc_property", "--site-url", "site_url"),
    "google.gsc-aggregate": ("gsc_property", "--site-url", "site_url"),
    "google.ga4-report": ("ga4_property", "--property-id", "property"),
    "render.page": ("web_url", "--url", "url"),
    "render.screenshot": ("web_url", "--url", "url"),
    "links.commoncrawl": ("domain", "--domain", "domain"),
    "domain.history": ("domain", "--domain", "domain"),
    "media.youtube-search": ("youtube_query", "--query", ""),
}


def _captured_target(options: dict[str, list[str]], data: JsonObject, observation: JsonObject,
                     reader: EvidenceRecords, subject: JsonObject) -> JsonObject:
    record = reader.read(observation.get("input_file"), kind="command_input", keys=INPUT_KEYS - {"kind"})
    target = captured_urls(record, argument_path=options["--urls"][0],
                           candidate=str(subject["candidate_commit"]),
                           digest=str(observation["prepared_subject_sha256"]),
                           platform=str(observation.get("platform")))
    urls = string_list(target["values"], "captured submission URLs", nonempty=True)
    if data.get("host") != urlsplit(urls[0]).hostname or data.get("url_count") != len(urls):
        raise ValueError("Actual IndexNow result disagrees with captured input host/count")
    if "urls" in data and normalize_target({"kind": "indexnow_url_set", "values": data["urls"]}) != target:
        raise ValueError("Actual IndexNow validation used a different URL set")
    return target


def command_target(command: str, argv: object, data: JsonObject, observation: JsonObject,
                   reader: EvidenceRecords, subject: JsonObject) -> JsonObject:
    """Bind real argv and canonical output, never read a captured path."""
    options = command_options(command, argv)
    if command in {"indexnow.validate", "indexnow.submit"}:
        target = _captured_target(options, data, observation, reader, subject)
        locations = options.get("--key-location")
        location = None if locations is None else locations[0]
        expected_location = None if location is None else normalize_target({"kind": "web_url", "value": location})["value"]
        if data.get("key_location") != expected_location:
            raise ValueError("IndexNow key-location output differs from its actual command")
        if command == "indexnow.submit" and urlsplit(options.get("--endpoint", ["https://api.indexnow.org/indexnow"])[0]).hostname != data.get("endpoint_host"):
            raise ValueError("IndexNow submission endpoint differs from actual argv")
        return target
    if command not in FIELDS:
        raise ValueError("Command has no reviewed remote target contract")
    kind, option, output = FIELDS[command]
    target = normalize_target({"kind": kind, "value": options[option][0]})
    if output and normalize_target({"kind": kind, "value": data.get(output)}) != target:
        raise ValueError("Actual command argv and result target do not agree")
    return target


def _grant(normalized: JsonObject, authorization: JsonObject) -> tuple[JsonObject, JsonObject]:
    target = normalize_target(authorization.get("target"))
    scope = normalize_scope(authorization.get("scope"))
    if (authorization.get("target_sha256") != target_digest(target)
            or authorization.get("scope_sha256") != scope_digest(scope)
            or normalize_target(normalized.get("target")) != target
            or normalized.get("target_sha256") != target_digest(target)
            or target not in object_list(scope["targets"], "granted targets")):
        raise ValueError("Concrete live target/scope bytes do not match their authorized digests")
    return target, scope


def _operation(command: str, request: JsonObject, target: JsonObject, data: JsonObject) -> None:
    host, method = request["endpoint_host"], request["method"]
    if command.startswith("render."):
        permitted = _web_operation(request, target)
    elif command == "domain.history":
        # Explicit scope plus pinned producer's actual IANA bootstrap selection,
        # not an invented fixed RDAP server list or caller-chosen transport.
        permitted = method == "GET"
    elif command in {"google.gsc-query", "google.gsc-aggregate", "google.ga4-report", "links.commoncrawl", "media.youtube-search"}:
        operations = {"google.gsc-query": ("POST", {"www.googleapis.com", "oauth2.googleapis.com"}),
                      "google.gsc-aggregate": ("POST", {"www.googleapis.com", "oauth2.googleapis.com"}),
                      "google.ga4-report": ("POST", {"analyticsdata.googleapis.com", "oauth2.googleapis.com"}),
                      "links.commoncrawl": ("GET", {"index.commoncrawl.org"}),
                      "media.youtube-search": ("GET", {"www.googleapis.com"})}
        expected, hosts = operations[command]
        permitted = method == expected and host in hosts
    else:
        permitted = command == "indexnow.submit" and method == "POST" and host == data.get("endpoint_host")
    if not permitted:
        raise ValueError("Actual request is not the canonical provider operation")


def _web_operation(request: JsonObject, target: JsonObject) -> bool:
    return (request["method"] == "GET" and target.get("kind") == "web_url"
            and request["endpoint_host"] == urlsplit(str(target["value"])).hostname)


def _request(request: JsonObject, *, commands: set[str], target: JsonObject, scope: JsonObject,
             data: JsonObject, authorization: JsonObject, observation: JsonObject,
             subject: JsonObject, now: datetime) -> str:
    exact_keys(request, {"request_id", "command_id", "method", "endpoint_host", "target", "http_status", "occurred_at"}, "actual request")
    identity = string_value(request["request_id"], "actual request identity")
    command = string_value(request["command_id"], "actual request command")
    if command not in commands:
        raise ValueError("Request is not associated with an actually observed command")
    host = normalize_host(request["endpoint_host"], allow_ip=True)
    concrete = normalize_target(request["target"])
    allowed = object_list(scope["targets"], "targets") + object_list(scope["redirect_targets"], "redirects", nonempty=False)
    if (host != request["endpoint_host"] or host not in string_list(scope["endpoint_hosts"], "granted hosts")
            or request["method"] not in string_list(scope["methods"], "granted methods") or concrete not in allowed):
        raise ValueError("Actual request is outside the concrete host/method/target grant")
    if not command.startswith("render.") and concrete != target:
        raise ValueError("Provider request used a different property/domain/query/URL set")
    status = request["http_status"]
    if status is not None and (type(status) is not int or status < 0):
        raise ValueError("Actual response status is not nullable nonbool integer metadata")
    occurred = observed_time(request["occurred_at"], subject, now)
    if not (instant(authorization["starts_at"], "grant start") <= occurred
            < instant(authorization["expires_at"], "grant expiry")) or occurred > instant(observation["observed_at"], "observation time"):
        raise ValueError("A hidden request falls outside preparation/permission/observation time")
    _operation(command, request, concrete, object_value(data[command], "validated command data"))
    return identity


def _results(observation: JsonObject, normalized: JsonObject, reader: EvidenceRecords,
             subject: JsonObject, target: JsonObject, scope: JsonObject) -> tuple[set[str], JsonObject]:
    commands = set(string_list(observation["capabilities"], "actual commands", nonempty=True))
    argv = object_value(observation.get("argv"), "captured argv")
    exits = object_value(observation.get("exit_codes"), "actual command exits")
    envelopes = object_value(normalized.get("data"), "actual CLI envelopes")
    for value in (argv, exits, envelopes):
        exact_keys(value, commands, "actual command mapping")
    validated: JsonObject = {}
    allowed = object_list(scope["targets"], "targets") + object_list(scope["redirect_targets"], "redirects", nonempty=False)
    for command in sorted(commands):
        if type(exits[command]) is not int or exits[command] != 0:
            raise ValueError("Actual capability process did not exit successfully")
        data = validate_result(command, envelopes[command])
        if command_target(command, argv[command], data, observation, reader, subject) != target:
            raise ValueError("Actual command used a target different from its concrete grant")
        if command.startswith("render.") and normalize_target({"kind": "web_url", "value": data["final_url"]}) not in allowed:
            raise ValueError("Rendered final URL is outside explicit redirect/target permission")
        validated[command] = data
    return commands, validated


def _telemetry(data: JsonObject, requests: list[JsonObject]) -> None:
    for command, value in data.items():
        result = object_value(value, "actual command result")
        actual = [row for row in requests if row["command_id"] == command]
        field = "attempts" if command == "indexnow.submit" else "request_count"
        if field in result and integer_value(result[field], "source actual request count") != len(actual):
            raise ValueError("Source request telemetry disagrees with its actual captured requests")
        if command == "indexnow.submit" and actual[-1]["http_status"] != result["http_status"]:
            raise ValueError("Submission receipt does not match the actual final response")


def validate_observation(observation: JsonObject, normalized: JsonObject,
                         authorization: JsonObject, reader: EvidenceRecords,
                         subject: JsonObject, now: datetime) -> None:
    integer_value(observation.get("job_id"), "actual observation job")
    if observation.get("platform") not in {"ubuntu", "windows"}:
        raise ValueError("Actual observation has no supported platform")
    target, scope = _grant(normalized, authorization)
    commands, data = _results(observation, normalized, reader, subject, target, scope)
    requests = object_list(normalized.get("requests"), "actual dispatched requests")
    if len(requests) > policy.MAX_RECORDS or integer_value(normalized.get("requests_made"), "actual request count") != len(requests):
        raise ValueError("Actual request inventory does not reconcile to the bounded count")
    identities: set[str] = set()
    covered: set[str] = set()
    for request in requests:
        identity = _request(request, commands=commands, target=target, scope=scope, data=data,
                            authorization=authorization, observation=observation, subject=subject, now=now)
        if identity in identities:
            raise ValueError("Duplicate actual request identity")
        identities.add(identity)
        covered.add(str(request["command_id"]))
    if covered != commands:
        raise ValueError("One or more alleged commands have no actual dispatched requests")
    _telemetry(data, requests)
