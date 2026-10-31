"""Synthetic preparation fixtures own their clock, not the host calendar."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_publication_prepare_execution import PreparationAPI, source_context, verify

from scripts import publication_prepare as preparation


@pytest.mark.parametrize("host_now", [
    datetime(2026, 11, 2, 3, tzinfo=UTC),
    datetime(2041, 7, 9, 3, tzinfo=UTC),
])
def test_positive_preparation_fixture_remains_deterministic_after_its_recorded_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host_now: datetime,
) -> None:
    class HostClock:
        @classmethod
        def now(cls, zone):
            assert zone is UTC
            return host_now

    monkeypatch.setattr(preparation, "datetime", HostClock)
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    expected = api.install_archive()
    output = tmp_path / "verified"
    result = verify(root, api, output)
    assert result["state"] == "PREPARED_VERIFIED_INTERNAL"
    assert {path.name: path.read_bytes() for path in output.iterdir()} == expected
