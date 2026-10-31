"""Whole counterfactual lifecycle: provider results are synthetic, validators real."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from adapters.mcp_extensions import REGISTRY
from scripts import publication_authorize as authorization
from scripts import publication_completion as completion
from scripts import publication_context as context
from scripts import publication_execution as execution
from scripts import publication_git as git_io
from scripts import publication_jobs as jobs
from scripts import publication_policy as policy
from scripts import publication_prerequisites as prerequisites
from scripts import publication_provider as provider
from scripts import publication_publish as publisher
from scripts import publication_subject as subjects
from scripts.publication_artifacts import verify_attestation
from scripts.publication_authorize import canonical
from scripts.publication_bundle import verify_bytes
from scripts.publication_evidence import checked_evidence
from scripts.publication_git import read_evidence
from tests.publication_full_path_fixtures import (
    COMPLETION_ARTIFACT,
    NOW,
    PREFIX,
    PUBLICATION_RUN,
    SELECTION,
    CounterfactualPublication,
    digest,
    stamp,
)
from tests.test_publication_artifacts import zip_bytes
from tests.test_publication_benchmark import rewrite_records


@pytest.fixture
def universe(tmp_path):
    source_registry = Path(__file__).resolve().parents[1] / "governance/publication-execution-authorities.json"
    original_registry = source_registry.read_bytes()
    original_bing = REGISTRY["bing-webmaster"]
    assert original_bing.live_state == "BLOCKED_BY_CONTRACT"
    assert all(not rows for rows in authorization.execution_authorities(source_registry.parents[1]).values())
    modeled = CounterfactualPublication(tmp_path)
    pristine_data, pristine_records = deepcopy(modeled.evidence), dict(modeled.records)
    with pytest.raises(ValueError, match="Bing source contract"):
        checked_evidence(canonical(pristine_data), pristine_records, modeled.subject,
                         subject_sha256=modeled.subject_digest, now=NOW)
    with pytest.MonkeyPatch.context() as scoped:
        modeled.install(scoped)
        scoped.setitem(REGISTRY, "bing-webmaster", replace(original_bing, live_state="CONFIGURABLE"))
        modeled.scope = scoped
        yield modeled
    assert source_registry.read_bytes() == original_registry
    assert REGISTRY["bing-webmaster"] is original_bing
    with pytest.raises(ValueError, match="Bing source contract"):
        checked_evidence(canonical(pristine_data), pristine_records, modeled.subject,
                         subject_sha256=modeled.subject_digest, now=NOW)


def observe(universe):
    universe.phase = "complete"
    universe.scope.setenv("GITHUB_JOB", "complete")
    output = universe.directory / "detached-completion"
    receipt = completion.observe_completion(universe.root, universe.api, selection=SELECTION,
                                           output=output, now=NOW)
    raw = (output / completion.MEMBER).read_bytes()
    universe.install_completion(raw)
    return receipt


def consume(universe):
    return completion.verify_completion(universe.root, universe.api, publication_run_id=PUBLICATION_RUN,
                                        artifact_id=COMPLETION_ARTIFACT, now=NOW)


def test_counterfactual_positive_uses_genuine_validators_through_detached_success(universe):
    validators = [authorization.authorize_candidate, read_evidence, checked_evidence,
                  execution.authenticate_execution, jobs.authenticate_jobs, verify_bytes,
                  verify_attestation, context.workflow_context, publisher.publish_candidate,
                  completion.observe_completion, completion.verify_completion,
                  authorization.execution_authorities, git_io.git, provider.authenticate_ci,
                  provider.authenticate_preparation, provider.authenticate_decisions,
                  prerequisites.job_claims, subjects.parse_subject]
    calls = {function.__code__: 0 for function in validators}

    def profile(frame, event, _argument):
        if event == "call" and frame.f_code in calls:
            calls[frame.f_code] += 1

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        candidate = authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
        assert candidate.bundle.files == universe.files
        published = publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
        assert published["state"] == "PUBLISHED_UNCERTIFIED" and published["publication_allowed"] is False
        receipt = observe(universe)
        assert receipt["state"] == "COMPLETION_OBSERVED" and universe.phase == "complete"
        with pytest.raises(ValueError, match="latest successful attempt mismatch"):
            consume(universe)
        universe.phase = "completed"
        approved = consume(universe)
    finally:
        sys.setprofile(previous)
    assert all(count > 0 for count in calls.values()), "No semantic validator may be replaced by a success stub"
    assert approved["state"] == "APPROVED" and approved["publication_allowed"] is True
    assert approved["gate_observations"] == policy.required_gate_values()
    assert approved["distribution_closure"] == "VERIFIED_PARITY"
    assert len(approved["publication"]["assets"]) == len(universe.files) == 6
    assert {row["name"]: universe.asset_data[identity] for identity, row in universe.assets.items()} == universe.files
    assert len(universe.writes) == 9  # tag, new draft, six uploads, one public PATCH
    assert any(command[:1] == ("diff-tree",) for command in universe.git_process.calls)
    assert len(universe.attestations) >= 11


@pytest.mark.parametrize("mutation,match", [
    ("owner-edit", "edited"), ("review-revoked", "not approved"),
    ("main-moved", "exact protected main"), ("evidence-source-change", "exact evidence head"),
    ("producer-failed", "latest successful attempt mismatch"),
    ("producer-source", "latest successful attempt mismatch"),
])
def test_counterfactual_initial_revocations_prevent_every_provider_write(universe, mutation, match):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    if mutation == "owner-edit":
        universe.graph["data"]["node"]["lastEditedAt"] = "2026-10-31T02:03:00Z"
    elif mutation == "review-revoked":
        universe.responses[PREFIX + "/pulls/77/reviews?per_page=100&page=1"][0]["state"] = "DISMISSED"
    elif mutation == "main-moved":
        universe.responses[PREFIX + "/branches/main"]["commit"]["sha"] = "f" * 40
    elif mutation == "evidence-source-change":
        universe.responses[PREFIX + "/pulls/77"]["head"]["sha"] = "f" * 40
        universe.git_process.evidence_alias = "f" * 40
    else:
        entry = universe.authorities["external_reproduction"][0]
        path = f"/repos/{entry['repository']}/actions/runs/43"
        if mutation == "producer-source":
            universe.responses[path]["head_sha"] = universe.subject["candidate_commit"]
        else:
            universe.responses[path]["conclusion"] = "failure"
    with pytest.raises(ValueError, match=match):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert universe.writes == []


@pytest.mark.parametrize("point,permitted_writes", [("destination", 0), ("draft", 2), ("readback", 8)])
def test_counterfactual_revocation_during_prerequisite_reads_prevents_next_mutation(
    universe, point, permitted_writes,
):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    revoked = []

    def revoke(endpoint):
        trigger = ((point == "destination" and "/git/matching-refs/tags/" in endpoint)
                   or (point == "draft" and "/releases/81/assets?" in endpoint)
                   or (point == "readback" and "/releases/assets/" in endpoint))
        if trigger and not revoked:
            universe.graph["data"]["node"]["lastEditedAt"] = stamp(3)
            revoked.append(len(universe.writes))

    universe.on_read = revoke
    with pytest.raises(ValueError, match="edited"):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert revoked == [permitted_writes]
    assert len(universe.writes) == permitted_writes
    assert not any(method == "PATCH" for method, _endpoint in universe.writes)


@pytest.mark.parametrize("origin", ["prepared", "producer"])
def test_counterfactual_corrupt_authenticated_archive_bytes_prevent_every_write(universe, origin):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    if origin == "prepared":
        endpoint = PREFIX + "/actions/artifacts/88/zip"
    else:
        entry = universe.authorities["external_reproduction"][0]
        endpoint = f"/repos/{entry['repository']}/actions/artifacts/100/zip"
    universe.archives[endpoint] += b"corruption"
    with pytest.raises(ValueError, match="authenticated provider digest"):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert universe.writes == []


@pytest.mark.parametrize("failure", ["job-platform", "job-interval", "request-before-health"])
def test_counterfactual_real_job_and_request_chronology_guards_cannot_be_sealed_away(universe, failure):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    expected = {"job-platform": "actual hosted runner", "job-interval": "actual successful job interval",
                "request-before-health": "joint capability proof"}[failure]
    if failure == "request-before-health":
        def early_request(row):
            if row.get("kind") == "normalized_observation" and row.get("request_id") == "render.page-ubuntu":
                row["requests"][0]["occurred_at"] = stamp(-3)
            return row

        universe.evidence, universe.records = rewrite_records(universe.evidence, universe.records, early_request)
        universe.reseal_evidence()  # All records/seals/E/decisions are coherently rebound; no stale-hash denial.
    else:
        entry = universe.authorities["live_authorized_smokes"][0]
        path = f"/repos/{entry['repository']}/actions/runs/41/attempts/1/jobs?per_page=100&page=1"
        job = universe.responses[path]["jobs"][0]
        if failure == "job-platform":
            job["labels"] = ["windows-latest"]
        else:
            job.update(started_at=stamp(6), completed_at=stamp(10))
    with pytest.raises(ValueError, match=expected):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert universe.writes == []


def test_counterfactual_oversize_prepared_member_is_rejected_before_first_irreversible_write(universe):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    files = dict(universe.files)
    wheel = next(name for name in files if name.endswith(".whl"))
    files[wheel] = b"X" * (policy.MAX_MEMBER_BYTES + 1)
    files["SHA256SUMS"] = "".join(
        f"{digest(raw)}  {name}\n" for name, raw in sorted(files.items())
        if name not in {"publication-subject.json", "SHA256SUMS"}
    ).encode()
    subject = json.loads(files["publication-subject.json"])
    for row in subject["files"]:
        row.update(bytes=len(files[row["name"]]), sha256=digest(files[row["name"]]))
    files["publication-subject.json"] = canonical(subject) + b"\n"
    archive = zip_bytes(files)
    endpoint = PREFIX + "/actions/artifacts/88"
    universe.responses[endpoint].update(digest="sha256:" + digest(archive), size_in_bytes=len(archive))
    universe.archives[endpoint + "/zip"] = archive
    with pytest.raises(ValueError, match="oversized members"):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert universe.writes == [] and universe.tag is None and universe.release is None
    assert ("GET", endpoint[1:] + "/zip") in universe.calls


@pytest.mark.parametrize("failure", ["receipt-binding", "public-bytes", "producer-job"])
def test_counterfactual_detached_consumer_rechecks_receipt_public_bytes_and_whole_producer(universe, failure):
    publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    receipt = observe(universe)
    universe.phase = "completed"
    assert consume(universe)["state"] == "APPROVED"
    writes_before = list(universe.writes)
    if failure == "receipt-binding":
        receipt["decisions_sha256"] = "0" * 64
        universe.install_completion(canonical(receipt) + b"\n")
        expected = "authorization was changed or revoked"
    elif failure == "public-bytes":
        identity = next(identity for identity, row in universe.assets.items() if row["name"].endswith(".whl"))
        universe.asset_data[identity] = universe.asset_data[identity][::-1]
        expected = "downloaded release bytes differ"
    else:
        universe.job_overrides["complete"] = {"conclusion": "failure"}
        expected = "unique successful certification job"
    with pytest.raises(ValueError, match=expected):
        consume(universe)
    assert universe.writes == writes_before


def test_counterfactual_expiry_remains_a_real_guard_not_a_fixture_approval(universe):
    authorization.authorize_candidate(universe.root, universe.api, **SELECTION, now=NOW)
    universe.clock.current = NOW.replace(year=2027)
    with pytest.raises(ValueError, match="expired"):
        publisher.publish_candidate(universe.root, universe.api, selection=SELECTION)
    assert universe.writes == []
