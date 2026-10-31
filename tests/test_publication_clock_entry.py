"""Actual wrapper-clock controls with explicit IO/authority stand-ins, no sleeps."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_publication_prepare_execution import NOW, PreparationAPI, source_context, verify

from scripts import publication_authorize as authorization
from scripts import publication_completion as completion
from scripts import publication_prepare as preparation
from scripts.publication_freshness import record_interval


def clock_type(start: datetime):
    class Clock:
        current = start

        @classmethod
        def now(cls, zone):
            assert zone is UTC
            return cls.current

    return Clock


@pytest.mark.parametrize("kind", ["authorize", "observe", "consume"])
def test_clock_regression_during_verification_is_rejected_even_inside_valid_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    entered = datetime.now(UTC)
    clock = clock_type(entered)
    module = authorization if kind == "authorize" else completion
    monkeypatch.setattr(module, "datetime", clock)

    def verified_io_seam(*_args, **kwargs):
        record_interval(valid_after=entered - timedelta(hours=1), valid_before=entered + timedelta(hours=1))
        clock.current = entered - timedelta(minutes=1)
        if kind == "authorize":
            return SimpleNamespace(temporal_proof=kwargs["temporal_proof"])
        return {"state": "COMPLETION_OBSERVED" if kind == "observe" else "APPROVED"}

    seam = {"authorize": "_authorize_candidate", "observe": "_observe_completion", "consume": "_verify_completion"}[kind]
    monkeypatch.setattr(module, seam, verified_io_seam)
    with pytest.raises(ValueError, match="regressed"):
        if kind == "authorize":
            authorization.authorize_candidate(tmp_path, None, prepare_run_id=1, artifact_id=2,
                                                evidence_pr=3, owner_comment_id=4, now=entered)
        elif kind == "observe":
            completion.observe_completion(tmp_path / "source", None, selection={},
                                           output=tmp_path / "receipt", now=entered)
        else:
            completion.verify_completion(tmp_path, None, publication_run_id=1, artifact_id=2, now=entered)
    assert not (tmp_path / "receipt" / completion.MEMBER).exists()


def test_preparation_actual_clock_expiry_during_download_writes_no_verified_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    clock = clock_type(NOW)
    monkeypatch.setattr(preparation, "datetime", clock)
    original = api.binary

    def download_then_expire(endpoint, limit):
        data = original(endpoint, limit)
        clock.current = NOW + timedelta(days=2)
        return data

    monkeypatch.setattr(api, "binary", download_then_expire)
    output = tmp_path / "verified"
    with pytest.raises(ValueError, match="expired"):
        verify(root, api, output)
    assert not output.exists() or not any(output.iterdir())


def test_observation_clock_expiry_during_receipt_write_never_returns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = datetime.now(UTC)
    clock = clock_type(entered)
    monkeypatch.setattr(completion, "datetime", clock)

    def verified_io_seam(*_args, **_kwargs):
        record_interval(valid_after=entered - timedelta(hours=1), valid_before=entered + timedelta(seconds=1))
        return {"state": "COMPLETION_OBSERVED"}

    original = Path.write_bytes

    def write_then_expire(path, data):
        result = original(path, data)
        clock.current = entered + timedelta(seconds=2)
        return result

    monkeypatch.setattr(completion, "_observe_completion", verified_io_seam)
    monkeypatch.setattr(Path, "write_bytes", write_then_expire)
    with pytest.raises(ValueError, match="expired"):
        completion.observe_completion(tmp_path / "source", None, selection={},
                                       output=tmp_path / "receipt", now=entered)
    assert (tmp_path / "receipt" / completion.MEMBER).exists(), "Postwrite denial does not pretend atomic cleanup"
