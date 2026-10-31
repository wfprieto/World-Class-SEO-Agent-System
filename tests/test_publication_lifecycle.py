"""Receipt-value and write-order regressions; state fakes are not authority proof."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import publication_authorize as authorization
from scripts import publication_completion as completion
from scripts import publication_policy as policy
from scripts import publication_publish as publisher
from scripts.publication_authorize import AuthorizedCandidate
from scripts.publication_bundle import CandidateBundle
from scripts.publication_freshness import collect_time_proof, record_interval
from tests.test_publication_artifacts import bundle_files
from tests.test_publication_provider import NOW


def _receipt() -> dict[str, object]:
    return {"schema_version": "1.0.0", "state": "COMPLETION_OBSERVED",
            "repository": policy.REPOSITORY, "repository_id": policy.REPOSITORY_ID,
            "binding": {}, "publication_run_id": 55, "publication_attempt": 1,
            "observed_at": NOW.isoformat(), "publication": {}, "decisions_sha256": "d" * 64,
            "gate_observations": {gate: "APPROVE_GREAT" if gate in policy.REVIEWERS else "PASS"
                                  for gate in policy.REQUIRED_GATES}}


def test_completion_retains_existing_canonical_reviewer_gate_values() -> None:
    value = _receipt()
    assert completion._receipt(json.dumps(value).encode(), 55, NOW) == value


def test_pass_labels_cannot_replace_actual_approve_great_role_values() -> None:
    value = _receipt()
    value["gate_observations"] = dict.fromkeys(policy.REQUIRED_GATES, "PASS")
    with pytest.raises(ValueError):
        completion._receipt(json.dumps(value).encode(), 55, NOW)


class StateAPI:
    """No network or credentials: records only the orchestration's fake mutations."""

    def __init__(self) -> None:
        self.revoked = False
        self.events: list[tuple[str, str]] = []

    def write(self, path: str, payload: dict[str, object], *, method: str = "POST") -> object:
        self.events.append((method, path))
        return {}


def _candidate() -> AuthorizedCandidate:
    files = bundle_files()
    bundle = CandidateBundle(json.loads(files["publication-subject.json"]), files, 88, "d" * 64)
    now = datetime.now(UTC)
    with collect_time_proof() as proof:
        record_interval(valid_after=now - timedelta(days=1), valid_before=now + timedelta(days=1))
    return AuthorizedCandidate(bundle, 90, "e" * 40, "f" * 64, 901, {}, {}, proof)


@pytest.mark.parametrize("point", ["destination", "draft_inventory", "asset_readback"])
def test_revocation_during_prerequisite_work_stops_the_next_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str,
) -> None:
    api = StateAPI()
    candidate = _candidate()
    monkeypatch.setattr(publisher, "workflow_context", lambda *args: ("a" * 40, 55, 1))

    def authorize(*args: object, **kwargs: object) -> AuthorizedCandidate:
        if api.revoked:
            raise ValueError("Synthetic authorization revoked during prerequisite work")
        return candidate

    def boundary(name: str) -> None:
        if point == name:
            api.revoked = True
            api.events.append(("REVOKED", name))

    def upload(*args: object) -> int:
        api.events.append(("UPLOAD", "asset"))
        return len(api.events)

    monkeypatch.setattr(publisher, "authorize_candidate", authorize)
    monkeypatch.setattr(publisher, "unused_destination", lambda *args: boundary("destination"))
    monkeypatch.setattr(publisher, "observed_tag", lambda *args: {})
    monkeypatch.setattr(publisher, "_new_draft", lambda *args: 81)
    monkeypatch.setattr(publisher, "_draft", lambda *args: boundary("draft_inventory"))
    monkeypatch.setattr(publisher, "_upload", upload)
    monkeypatch.setattr(publisher, "observed_release",
                        lambda *args, **kwargs: boundary("asset_readback") or {})
    with pytest.raises(ValueError, match="revoked"):
        publisher.publish_candidate(tmp_path, api, selection=candidate.selection())
    revoked = next(index for index, event in enumerate(api.events) if event[0] == "REVOKED")
    assert api.events[revoked + 1:] == [], "No write may follow the failed prerequisite recheck"


def test_expiry_during_final_authentication_prevents_even_the_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = StateAPI()
    baseline = _candidate()
    calls = []

    def authorize(*args: object, **kwargs: object) -> AuthorizedCandidate:
        calls.append(1)
        if len(calls) == 1:
            return baseline
        now = datetime.now(UTC)
        with collect_time_proof() as proof:
            record_interval(valid_after=now - timedelta(seconds=1), valid_before=now + timedelta(milliseconds=20))
        time.sleep(0.04)
        return replace(baseline, temporal_proof=proof)

    monkeypatch.setattr(publisher, "workflow_context", lambda *args: ("a" * 40, 55, 1))
    monkeypatch.setattr(publisher, "authorize_candidate", authorize)
    monkeypatch.setattr(publisher, "unused_destination", lambda *args: None)
    monkeypatch.setattr(api, "write", lambda *args, **kwargs:
                        pytest.fail("Expired authorization reached an irreversible mutation"))
    with pytest.raises(ValueError, match="expired"):
        publisher.publish_candidate(tmp_path, api, selection=baseline.selection())
    assert len(calls) == 2 and api.events == []


def test_authorization_factory_does_not_accept_a_start_clock_after_work_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _candidate()

    def checked(*args: object, **kwargs: object) -> AuthorizedCandidate:
        now = datetime.now(UTC)
        record_interval(valid_after=now - timedelta(seconds=1), valid_before=now + timedelta(milliseconds=20))
        time.sleep(0.04)
        return baseline

    monkeypatch.setattr(authorization, "_authorize_candidate", checked)
    with pytest.raises(ValueError, match="expired"):
        authorization.authorize_candidate(tmp_path, StateAPI(), **baseline.selection(), now=datetime.now(UTC))
