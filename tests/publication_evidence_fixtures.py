"""Explicit synthetic/counterfactual packets, never observed execution evidence."""

from copy import deepcopy
from datetime import timedelta

from test_publication_benchmark import pack_record

from scripts import publication_policy as policy
from tests.test_publication_arguments import valid_argv
from tests.test_publication_capability_checks import COMMAND_TARGET, packet
from tests.test_publication_capability_results import synthetic_bing_success, valid_result

FAMILIES = {
    "google.gsc-query": ("gsc-live", "google-search-console"),
    "google.gsc-aggregate": ("gsc-live", "google-search-console"),
    "google.ga4-report": ("ga4-live", "google-analytics-data"),
    "render.page": ("render-installable", "authorized-public-web"),
    "render.screenshot": ("render-installable", "authorized-public-web"),
    "links.commoncrawl": ("commoncrawl-authority", "rdap-common-crawl"),
    "domain.history": ("domain-history", "rdap-common-crawl"),
    "media.youtube-search": ("youtube-search", "youtube-data"),
    "indexnow.submit": ("bing-indexnow", "indexnow"),
}


def _input(records, reader, bound):
    return pack_record(records, {**deepcopy(next(iter(reader.values.values()))), **bound})


def _observation(records, bound, command, platform, now):
    observation, normalized, authorization, reader = packet(command)
    family, provider = FAMILIES[command]
    group = command + "-" + platform
    job = 123 if platform == "ubuntu" else 456
    authorization.update({**bound, "kind": "live_authorization", "owner_actor_id": policy.OWNER_ID,
        "starts_at": (now - timedelta(minutes=4)).isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(), "max_requests": 64,
        "max_cost_micros": 0, "cost_approved": provider == "youtube-data",
        "write_approved": provider == "indexnow"})
    normalized.update({**bound, "kind": "normalized_observation", "capabilities": [command],
        "provider_id": provider, "request_id": group, "observed_at": now.isoformat(),
        "cost_micros": 0, "write_performed": provider == "indexnow"})
    for index, request in enumerate(normalized["requests"]):
        request.update({"request_id": f"{group}-{index}", "occurred_at": (now - timedelta(seconds=10)).isoformat()})
    observation.update({**bound, "kind": "live_observation", "mode": "AUTHORIZED_LIVE",
        "platform": platform, "job_id": job, "provider_id": provider, "request_id": group,
        "observed_at": now.isoformat(), "authorization": pack_record(records, authorization),
        "normalized": pack_record(records, normalized)})
    if command == "indexnow.submit":
        observation["input_file"] = _input(records, reader, bound)
    for role in ("provider", "application"):
        observation[f"{role}_log"] = pack_record(records, {**bound, "kind": "live_log",
            "role": role, "request_id": group, "request_ids": [row["request_id"] for row in normalized["requests"]],
            "observed_at": now.isoformat(), "source_sha256": "7" * 64, "redacted": True,
            "events": ["Explicitly synthetic test-only capture; not actual provider logs."]})
    return family, pack_record(records, observation)


def _prerequisite(records, bound, command, platform, now):
    render = command in {"browser.install", "render.health"}
    row = {**bound, "kind": "capability_prerequisite", "capability_id": "render-installable" if render else "bing-indexnow",
           "command_id": command, "platform": platform, "job_id": 123 if platform == "ubuntu" else 456,
           "executed_at": (now - timedelta(minutes=3 if command == "browser.install" else 2)).isoformat(),
           "argv": valid_argv(command), "exit_code": 0}
    if command == "browser.install":
        row["result"] = {"installed": True, "binary_sha256": "8" * 64, "browser_version": "SYNTHETIC Chromium",
                         "output_bytes": 128, "stdout_sha256": "9" * 64, "stderr_sha256": "0" * 64}
    elif command == "bing.preflight":
        row["result"] = synthetic_bing_success()
    else:
        row["result"] = valid_result(command)
    if command == "indexnow.validate":
        row["result"]["data"]["urls"] = ["https://example.com/a"]
        _observation_data, _normalized, _authorization, reader = packet("indexnow.submit")
        row["input_file"] = _input(records, reader, bound)
    return row["capability_id"], pack_record(records, row)


def live_fixture(records, bound, now):
    observations, prerequisites = [], []
    families = {identity: [] for identity, _provider in FAMILIES.values()}
    for command in COMMAND_TARGET:
        platforms = ("ubuntu", "windows") if command.startswith("render.") else ("ubuntu",)
        for platform in platforms:
            family, reference = _observation(records, bound, command, platform, now)
            observations.append(reference)
            families[family].append(reference)
    for command, platform in (("browser.install", "ubuntu"), ("render.health", "ubuntu"),
            ("browser.install", "windows"), ("render.health", "windows"),
            ("bing.preflight", "ubuntu"), ("indexnow.validate", "ubuntu")):
        family, reference = _prerequisite(records, bound, command, platform, now)
        prerequisites.append(reference)
        families[family].append(reference)
    return observations, prerequisites, [(family, "live_authorized_smokes", refs) for family, refs in families.items()]
