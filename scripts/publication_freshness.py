"""Ephemeral time-only evidence; never substitutes for provider authority."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


def _utc(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError("Temporal proof requires an actual timezone-aware UTC clock")


@dataclass(slots=True)
class TemporalProof:
    """Only validated times; construction accepts no caller/wire-supplied bounds."""

    _after: datetime | None = field(default=None, init=False, repr=False)
    _before: datetime | None = field(default=None, init=False, repr=False)
    _last: datetime | None = field(default=None, init=False, repr=False)

    def _include(self, valid_after: datetime, valid_before: datetime) -> None:
        self._after = max(self._after, valid_after) if self._after else valid_after
        self._before = min(self._before, valid_before) if self._before else valid_before

    def assert_current(self, now: datetime) -> None:
        _utc(now)
        if self._after is None or self._before is None:
            raise ValueError("Empty temporal proof cannot certify current validity")
        if not self._after <= now < self._before or (self._last is not None and now < self._last):
            raise ValueError("Temporal proof has expired, regressed or is not yet valid")
        self._last = now


_ACTIVE: ContextVar[tuple[TemporalProof, ...]] = ContextVar("publication_time_proofs", default=())


@contextmanager
def collect_time_proof() -> Iterator[TemporalProof]:
    proof = TemporalProof()
    reset = _ACTIVE.set((*_ACTIVE.get(), proof))
    try:
        yield proof
    finally:
        _ACTIVE.reset(reset)


def record_interval(*, valid_after: datetime, valid_before: datetime) -> None:
    _utc(valid_after)
    _utc(valid_before)
    if valid_after >= valid_before:
        raise ValueError("Temporal evidence must have a nonempty valid interval")
    for proof in _ACTIVE.get():
        proof._include(valid_after, valid_before)


def record_freshness(issued: datetime, *, ttl: int, skew: int) -> None:
    """Record an already-validated window, bounded to representable UTC dates."""
    if not _ACTIVE.get():
        return
    try:
        after = issued - timedelta(seconds=skew)
    except OverflowError:
        after = datetime.min.replace(tzinfo=UTC)
    try:
        before = issued + timedelta(seconds=ttl)
    except OverflowError:
        before = datetime.max.replace(tzinfo=UTC) if ttl >= 0 else datetime.min.replace(tzinfo=UTC)
    record_interval(valid_after=after, valid_before=before)
