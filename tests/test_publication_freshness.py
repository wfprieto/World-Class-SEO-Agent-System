"""Ephemeral time intersection, real expiry, and validator-hook coverage."""

from __future__ import annotations

import time
from contextvars import Context
from datetime import UTC, datetime, timedelta, timezone

import pytest

from scripts.publication_freshness import collect_time_proof, record_interval
from scripts.publication_provider import authenticate_preparation, fresh_window
from scripts.publication_subject import require_fresh
from tests.test_publication_provider import (
    PREFIX,
    FixtureAPI,
    preparation_responses,
    subject,
)
from tests.test_publication_reviews import authorize, decisions_responses

NOW = datetime(2026, 10, 31, 3, tzinfo=UTC)


def interval(start: int, end: int) -> None:
    record_interval(valid_after=NOW + timedelta(seconds=start),
                    valid_before=NOW + timedelta(seconds=end))


def test_real_clock_expiry_during_work_rejects_final_time_proof() -> None:
    started = datetime.now(UTC)
    with collect_time_proof() as proof:
        record_interval(valid_after=started - timedelta(seconds=1),
                        valid_before=started + timedelta(milliseconds=20))
        time.sleep(0.04)
    with pytest.raises(ValueError):
        proof.assert_current(datetime.now(UTC))


def test_nested_intersections_propagate_and_scope_restores_after_exception() -> None:
    with collect_time_proof() as outer:
        interval(-10, 20)
        with pytest.raises(RuntimeError), collect_time_proof() as inner:
            interval(-5, 10)
            raise RuntimeError("synthetic interrupted validation")
        interval(-20, 15)
    outer.assert_current(NOW + timedelta(seconds=9))
    inner.assert_current(NOW + timedelta(seconds=9))
    for proof in (outer, inner):
        with pytest.raises(ValueError):
            proof.assert_current(NOW + timedelta(seconds=10))
    with collect_time_proof() as empty:
        pass
    with pytest.raises(ValueError, match="Empty"):
        empty.assert_current(NOW)


@pytest.mark.parametrize("lower,upper", [(1, 1), (2, 1)])
def test_empty_or_reversed_intervals_fail_closed(lower: int, upper: int) -> None:
    with collect_time_proof(), pytest.raises(ValueError):
        interval(lower, upper)


def test_lower_bound_is_inclusive_and_upper_bound_is_exclusive() -> None:
    with collect_time_proof() as proof:
        interval(0, 10)
    with pytest.raises(ValueError):
        proof.assert_current(NOW - timedelta(microseconds=1))
    proof.assert_current(NOW)
    with pytest.raises(ValueError):
        proof.assert_current(NOW + timedelta(seconds=10))


def test_disjoint_validated_bounds_and_regressed_clock_fail() -> None:
    with collect_time_proof() as disjoint:
        interval(-2, -1)
        interval(1, 2)
    with pytest.raises(ValueError):
        disjoint.assert_current(NOW)
    with collect_time_proof() as proof:
        interval(-10, 10)
    proof.assert_current(NOW)
    with pytest.raises(ValueError, match="regressed"):
        proof.assert_current(NOW - timedelta(microseconds=1))


@pytest.mark.parametrize("clock", [NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))])
def test_proof_rejects_non_utc_assertion_clock(clock: datetime) -> None:
    with collect_time_proof() as proof:
        interval(-10, 10)
    with pytest.raises(ValueError, match="UTC"):
        proof.assert_current(clock)


def test_context_local_collections_do_not_leak_into_other_candidates() -> None:
    with collect_time_proof() as outer:
        interval(-10, 10)
        Context().run(lambda: interval(-1, 1))
    outer.assert_current(NOW + timedelta(seconds=9))


def test_shared_subject_evidence_freshness_hook_collects_expiry() -> None:
    with collect_time_proof() as proof:
        require_fresh(NOW.isoformat(), now=NOW, ttl=1, label="subject/evidence time")
    proof.assert_current(NOW)
    with pytest.raises(ValueError):
        proof.assert_current(NOW + timedelta(seconds=1))


def test_provider_start_and_end_freshness_collect_tightest_bounds() -> None:
    start, end = NOW - timedelta(seconds=5), NOW + timedelta(seconds=1)
    with collect_time_proof() as proof:
        fresh_window({"run_started_at": start.isoformat(), "updated_at": end.isoformat()}, NOW, 10)
    proof.assert_current(end - timedelta(seconds=300))
    proof.assert_current(NOW + timedelta(seconds=4))
    with pytest.raises(ValueError):
        proof.assert_current(NOW + timedelta(seconds=5))


def test_explicit_artifact_expiry_is_not_lost_after_provider_validation() -> None:
    responses = preparation_responses()
    responses[PREFIX + "/actions/artifacts/88"]["expires_at"] = (NOW + timedelta(seconds=1)).isoformat()
    with collect_time_proof() as proof:
        authenticate_preparation(FixtureAPI(responses), subject(), artifact_id=88,
                                 archive_sha256="d" * 64, now=NOW)
    proof.assert_current(NOW)
    with pytest.raises(ValueError):
        proof.assert_current(NOW + timedelta(seconds=1))


def test_both_independent_roles_and_owner_bounds_propagate_through_existing_checks() -> None:
    with collect_time_proof() as proof:
        authorize(FixtureAPI(decisions_responses()))
    with pytest.raises(ValueError):
        proof.assert_current(NOW.replace(hour=2, minute=44))
    proof.assert_current(NOW.replace(hour=2, minute=45))
    proof.assert_current(NOW.replace(hour=2, minute=39) + timedelta(days=1))
    with pytest.raises(ValueError):
        proof.assert_current(NOW.replace(hour=2, minute=40) + timedelta(days=1))


def test_failed_freshness_validation_cannot_create_a_time_proof() -> None:
    with collect_time_proof() as proof, pytest.raises(ValueError):
        require_fresh((NOW - timedelta(days=1)).isoformat(), now=NOW, ttl=1, label="expired")
    with pytest.raises(ValueError, match="Empty"):
        proof.assert_current(NOW)


def test_time_hook_preserves_preexisting_representable_date_boundary() -> None:
    earliest = datetime.min.replace(tzinfo=UTC)
    with collect_time_proof() as proof:
        assert require_fresh(earliest.isoformat(), now=earliest, ttl=1, label="boundary") == earliest
    proof.assert_current(earliest)
