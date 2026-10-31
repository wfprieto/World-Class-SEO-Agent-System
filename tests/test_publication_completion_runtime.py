"""Completion ordering uses offline seams; it does not certify fake artifacts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import publication_completion as completion
from scripts.publication_freshness import record_interval
from tests.test_publication_lifecycle import _candidate


def test_revocation_during_public_readback_prevents_a_completion_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    revoked = []
    output = tmp_path / "completion"

    def authorize(*args: object, **kwargs: object):
        if revoked:
            raise ValueError("Synthetic owner decision revoked during readback")
        return candidate

    def readback(*args: object, **kwargs: object):
        revoked.append(True)
        return {}

    monkeypatch.setattr(completion, "workflow_context", lambda *args: ("a" * 40, 55, 1))
    monkeypatch.setattr(completion, "_dependencies", lambda *args: None)
    monkeypatch.setattr(completion, "authorize_candidate", authorize)
    monkeypatch.setattr(completion, "observed_release", readback)
    with pytest.raises(ValueError, match="revoked"):
        completion.observe_completion(tmp_path / "source", object(), selection=candidate.selection(),
                                      output=output, now=datetime.now(UTC))
    assert not (output / completion.MEMBER).exists()


def test_detached_consumer_checks_actual_clock_after_all_verification_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def observed(*args: object, **kwargs: object):
        now = datetime.now(UTC)
        record_interval(valid_after=now - timedelta(seconds=1), valid_before=now - timedelta(microseconds=1))
        return {"state": "APPROVED"}

    monkeypatch.setattr(completion, "_verify_completion", observed, raising=False)
    with pytest.raises(ValueError, match="expired"):
        completion.verify_completion(tmp_path, object(), publication_run_id=55,
                                     artifact_id=99, now=datetime.now(UTC))


def test_expiry_during_output_preflight_leaves_no_receipt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    output = tmp_path / "completion"

    def directory(*args: object) -> Path:
        output.mkdir()
        now = datetime.now(UTC)
        record_interval(valid_after=now - timedelta(seconds=1), valid_before=now - timedelta(microseconds=1))
        return output

    def authorize(*args: object, **kwargs: object):
        # Model the real validator's populated bounds before entry anchoring;
        # output preflight below still expires them before any receipt bytes.
        now = datetime.now(UTC)
        record_interval(valid_after=now - timedelta(hours=1), valid_before=now + timedelta(hours=1))
        return candidate

    monkeypatch.setattr(completion, "workflow_context", lambda *args: ("a" * 40, 55, 1))
    monkeypatch.setattr(completion, "_dependencies", lambda *args: None)
    monkeypatch.setattr(completion, "authorize_candidate", authorize)
    monkeypatch.setattr(completion, "observed_release", lambda *args: {})
    monkeypatch.setattr(completion, "output_directory", directory)
    with pytest.raises(ValueError, match="expired"):
        completion.observe_completion(tmp_path / "source", object(), selection=candidate.selection(),
                                      output=output, now=datetime.now(UTC))
    assert not (output / completion.MEMBER).exists()
