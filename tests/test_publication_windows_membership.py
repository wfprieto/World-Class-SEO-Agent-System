"""Synthetic kernel/clock contracts for real capture/wait/close, not OS proof."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

import pytest

from scripts import publication_process_windows as windows

BOUNDARY = "^Process membership exceeds its finite boundary$"
JOB_HANDLE = 41


def _handle(pid: int) -> int:
    return 1_000_000 + pid


@dataclass(frozen=True)
class Snapshot:
    assigned: int
    count: int
    pids: tuple[int, ...] = ()
    api_ok: bool = True
    elapsed: float = 0.0


class FakeClock:
    def __init__(self, *, now: float = 0.0, at_read: dict[int, float] | None = None):
        self.now = now
        self.at_read = at_read or {}
        self.reads = 0
        self.allow_sleep = False
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        self.reads += 1
        self.now = self.at_read.get(self.reads, self.now)
        return self.now  # Sticky after the last scheduled event; never exhausts.

    def sleep(self, seconds: float) -> None:
        assert self.allow_sleep, "capture must not add a sleep or time allowance"
        self.sleeps.append(seconds)
        self.now += seconds


class FakeKernel:
    def __init__(self, snapshots: list[Snapshot], clock: FakeClock, *,
                 denied: dict[int, int], open_elapsed: dict[int, float]):
        self.snapshots = snapshots
        self.clock = clock
        self.denied = denied
        self.open_elapsed = open_elapsed
        self.queries = 0
        self.opened: list[tuple[int, int, bool]] = []
        self.closed: list[int] = []
        self.waited: list[tuple[int, int]] = []
        self.pending_once: set[int] = set()

    def QueryInformationJobObject(self, handle, info, buffer, size, returned):
        assert handle == JOB_HANDLE and info == 3 and returned is None
        assert size == 8 + 4096 * ctypes.sizeof(ctypes.c_size_t)
        index = self.queries
        self.queries += 1
        assert index < len(self.snapshots), "unexpected extra membership query"
        row = self.snapshots[index]
        self.clock.now += row.elapsed
        if not row.api_ok:
            return 0
        ctypes.c_uint32.from_buffer(buffer, 0).value = row.assigned
        ctypes.c_uint32.from_buffer(buffer, 4).value = row.count
        for index, pid in enumerate(row.pids):
            assert index < min(row.count, 4096)
            ctypes.c_size_t.from_buffer(buffer, 8 + index * ctypes.sizeof(ctypes.c_size_t)).value = pid
        return 1

    def OpenProcess(self, rights: int, inherit: bool, pid: int) -> int:
        self.opened.append((pid, rights, inherit))
        assert rights == 0x100000 and inherit is False
        self.clock.now += self.open_elapsed.get(pid, 0.0)
        if pid in self.denied:
            if sys.platform == "win32":
                ctypes.set_last_error(self.denied[pid])  # Private ctypes TLS, no Win32 query.
            return 0
        return _handle(pid)

    def WaitForSingleObject(self, handle: int, milliseconds: int) -> int:
        self.waited.append((handle, milliseconds))
        assert milliseconds == 0
        if handle in self.pending_once:
            self.pending_once.remove(handle)
            return 258
        return 0

    def CloseHandle(self, handle: int) -> int:
        self.closed.append(handle)
        return 1


@pytest.fixture
def job_factory(monkeypatch: pytest.MonkeyPatch):
    previous_error = ctypes.get_last_error() if sys.platform == "win32" else None

    def make(snapshots: list[Snapshot], *, retained: int = 0,
             clock: FakeClock | None = None, denied: dict[int, int] | None = None,
             open_elapsed: dict[int, float] | None = None):
        local_clock = clock or FakeClock()
        kernel = FakeKernel(snapshots, local_clock, denied=denied or {},
                            open_elapsed=open_elapsed or {})
        job = object.__new__(windows.WindowsJob)  # Avoid actual Job creation in unit proof.
        job.kernel, job.handle, job.assigned = kernel, JOB_HANDLE, False
        job.members = {pid: _handle(pid) for pid in range(1, retained + 1)}
        monkeypatch.setattr(windows, "time", local_clock)  # Never mutate stdlib time.
        return job, kernel, local_clock

    try:
        yield make
    finally:
        if previous_error is not None:
            ctypes.set_last_error(previous_error)


@pytest.mark.parametrize("mode", ["empty", "new", "existing"])
def test_capture_complete_snapshot_and_existing_member_controls(job_factory, mode: str) -> None:
    pids = () if mode == "empty" else (1, 2)
    job, kernel, _ = job_factory([Snapshot(len(pids), len(pids), pids)],
                                retained=1 if mode == "existing" else 0)
    assert job.capture(1.0) is None
    assert kernel.queries == 1
    assert job.members == {pid: _handle(pid) for pid in pids}
    assert [pid for pid, _, _ in kernel.opened] == ([] if mode == "empty" else
                                                [2] if mode == "existing" else [1, 2])
    assert kernel.closed == []


@pytest.mark.parametrize("incomplete", [1, 2], ids=["one-partial", "two-partials"])
def test_capture_retries_incomplete_membership_until_complete(job_factory, incomplete: int) -> None:
    rows = [Snapshot(5, 4, (1, 2, 3, 4))] * incomplete + [Snapshot(5, 5, (1, 2, 3, 4, 5))]
    job, kernel, _ = job_factory(rows)
    assert job.capture(1.0) is None
    assert kernel.queries == incomplete + 1
    assert job.members == {pid: _handle(pid) for pid in range(1, 6)}
    assert [pid for pid, _, _ in kernel.opened] == [1, 2, 3, 4, 5]
    assert kernel.closed == []


@pytest.mark.parametrize("following", [(), (3, 4, 5)], ids=["partial-empty", "changed-set"])
def test_capture_keeps_partial_handles_when_snapshot_changes(job_factory, following) -> None:
    job, kernel, _ = job_factory([Snapshot(5, 4, (1, 2, 3, 4)),
                                 Snapshot(len(following), len(following), following)])
    assert job.capture(1.0) is None
    assert kernel.queries == 2
    expected = {1, 2, 3, 4} | set(following)
    assert job.members == {pid: _handle(pid) for pid in expected}
    assert [pid for pid, _, _ in kernel.opened] == sorted(expected)
    assert kernel.closed == []


def test_capture_incomplete_exhaustion_is_bounded(job_factory) -> None:
    rows = [Snapshot(5, 4, tuple(range(start, start + 4))) for start in (1, 2, 3)]
    job, kernel, _ = job_factory(rows)
    with pytest.raises(ValueError, match=BOUNDARY):
        job.capture(1.0)
    assert kernel.queries == 3  # A fourth query is an explicit FakeKernel assertion failure.
    assert job.members == {pid: _handle(pid) for pid in range(1, 7)}
    assert [pid for pid, _, _ in kernel.opened] == list(range(1, 7))
    assert kernel.closed == []


@pytest.mark.parametrize("after_partial", [False, True], ids=["first-api", "after-partial"])
def test_capture_api_failures_remain_fail_closed(job_factory, after_partial: bool) -> None:
    rows = ([Snapshot(5, 4, (1, 2, 3, 4))] if after_partial else [])
    job, kernel, _ = job_factory(rows + [Snapshot(0, 0, api_ok=False)])
    with pytest.raises(OSError, match="^Complete process membership is unavailable$") as failure:
        job.capture(1.0)
    assert type(failure.value) is OSError
    assert kernel.queries == (2 if after_partial else 1)
    assert job.members == ({pid: _handle(pid) for pid in range(1, 5)} if after_partial else {})
    assert kernel.closed == []


@pytest.mark.parametrize("assigned,count,retained", [
    pytest.param(0, 1, 0, id="assigned-below-count"),
    pytest.param(4097, 1, 0, id="assigned-over-cap-incomplete"),
    pytest.param(4097, 4097, 0, id="both-over-cap"),
    pytest.param(4096, 4097, 0, id="returned-over-cap"),
    pytest.param(4096, 4096, 4097, id="complete-conservative-sum-8193"),
    pytest.param(4096, 4095, 4098, id="incomplete-conservative-sum-8193"),
    pytest.param(1, 1, 8192, id="one-over-full-retained-cap"),
])
def test_capture_rejects_malformed_or_over_cap_before_array_access(
    job_factory, assigned: int, count: int, retained: int,
) -> None:
    job, kernel, _ = job_factory([Snapshot(assigned, count)], retained=retained)
    original = dict(job.members)
    with pytest.raises(ValueError, match=BOUNDARY):
        job.capture(1.0)
    assert kernel.queries == 1 and kernel.opened == []
    assert job.members == original and kernel.closed == []


@pytest.mark.parametrize("mode", ["new-4096", "sum-8192", "retained-8192", "partial-sum-8192"])
def test_capture_exact_capacity_and_retained_sum_boundaries(job_factory, mode: str) -> None:
    count = 0 if mode == "retained-8192" else 4095 if mode == "partial-sum-8192" else 4096
    retained = {"new-4096": 0, "sum-8192": 4096, "retained-8192": 8192,
                "partial-sum-8192": 4097}[mode]
    rows = [Snapshot(4096 if mode == "partial-sum-8192" else count,
                     count, tuple(range(1, count + 1)))]
    if mode == "partial-sum-8192":
        rows.append(Snapshot(0, 0))
    job, kernel, _ = job_factory(rows, retained=retained)
    assert job.capture(1.0) is None
    assert kernel.queries == (2 if mode == "partial-sum-8192" else 1)
    assert len(job.members) == max(retained, count)
    assert len(kernel.opened) == (4096 if mode == "new-4096" else 0)
    assert kernel.closed == []


@pytest.mark.parametrize("error", [5, 87], ids=["non87-denial", "existing-error87-policy"])
def test_capture_preserves_handles_on_open_process_denial(job_factory, error: int) -> None:
    job, kernel, _ = job_factory([Snapshot(3, 3, (1, 2, 3))], denied={2: error})
    if error == 87 and sys.platform == "win32":
        assert job.capture(1.0) is None
        assert job.members == {1: _handle(1), 3: _handle(3)}
    else:
        with pytest.raises(OSError, match="^Process completion cannot be authenticated$") as failure:
            job.capture(1.0)
        assert type(failure.value) is OSError
        assert job.members == {1: _handle(1)}
        assert [pid for pid, _, _ in kernel.opened] == [1, 2]
    assert kernel.queries == 1 and kernel.closed == []


@pytest.mark.parametrize("pids", [(), (1,)], ids=["expired-empty", "expired-nonempty"])
def test_capture_expired_deadline_never_queries(job_factory, pids) -> None:
    job, kernel, _ = job_factory([Snapshot(len(pids), len(pids), pids)], clock=FakeClock(now=1.0))
    with pytest.raises(TimeoutError, match="deadline"):
        job.capture(1.0)
    assert kernel.queries == 0 and kernel.opened == [] and job.members == {}


@pytest.mark.parametrize("pids", [(), (1,)], ids=["late-empty", "late-nonempty"])
def test_capture_checks_deadline_after_complete_empty_query(job_factory, pids) -> None:
    job, kernel, _ = job_factory([Snapshot(len(pids), len(pids), pids, elapsed=2.0)])
    with pytest.raises(TimeoutError, match="deadline"):
        job.capture(1.0)
    assert kernel.queries == 1 and kernel.opened == [] and job.members == {}


@pytest.mark.parametrize("slow_pid", [1, 2], ids=["before-next-pid", "late-final-handle"])
def test_capture_checks_deadline_after_last_handle(job_factory, slow_pid: int) -> None:
    job, kernel, _ = job_factory([Snapshot(2, 2, (1, 2))], open_elapsed={slow_pid: 2.0})
    with pytest.raises(TimeoutError, match="deadline"):
        job.capture(1.0)
    assert job.members == {pid: _handle(pid) for pid in range(1, slow_pid + 1)}
    assert [pid for pid, _, _ in kernel.opened] == list(range(1, slow_pid + 1))
    assert kernel.queries == 1 and kernel.closed == []


def test_capture_partial_then_empty_expiry_preserves_handles(job_factory) -> None:
    job, kernel, _ = job_factory([Snapshot(2, 1, (1,)), Snapshot(0, 0, elapsed=2.0)])
    with pytest.raises(TimeoutError, match="deadline"):
        job.capture(1.0)
    assert kernel.queries == 2 and job.members == {1: _handle(1)}
    assert kernel.closed == []


def test_capture_checks_deadline_between_queries(job_factory) -> None:
    clock = FakeClock(at_read={4: 1.0})
    job, kernel, _ = job_factory([Snapshot(1, 0)], clock=clock)
    with pytest.raises(TimeoutError, match="deadline"):
        job.capture(1.0)
    assert kernel.queries == 1 and job.members == {} and kernel.closed == []


@pytest.mark.parametrize("later", ["api", "header", "handle"])
def test_capture_retains_earlier_handles_on_later_error(job_factory, later: str) -> None:
    last = {"api": Snapshot(0, 0, api_ok=False), "header": Snapshot(0, 1, (3,)),
            "handle": Snapshot(1, 1, (3,))}[later]
    job, kernel, _ = job_factory([Snapshot(3, 2, (1, 2)), last], denied={3: 5})
    error = ValueError if later == "header" else OSError
    message = {"api": "^Complete process membership is unavailable$", "header": BOUNDARY,
               "handle": "^Process completion cannot be authenticated$"}[later]
    with pytest.raises(error, match=message) as failure:
        job.capture(1.0)
    assert type(failure.value) is error
    assert kernel.queries == 2 and job.members == {1: _handle(1), 2: _handle(2)}
    assert kernel.closed == []


@pytest.mark.parametrize("failure", ["api", "header", "handle"])
def test_capture_error_precedence_under_expiry(job_factory, failure: str) -> None:
    row = {"api": Snapshot(0, 0, api_ok=False, elapsed=2.0),
           "header": Snapshot(0, 1, (1,), elapsed=2.0),
           "handle": Snapshot(1, 1, (1,))}[failure]
    job, kernel, _ = job_factory([row], denied={1: 5},
                                open_elapsed={1: 2.0} if failure == "handle" else {})
    error = ValueError if failure == "header" else OSError
    message = BOUNDARY if failure == "header" else (
        "^Complete process membership is unavailable$" if failure == "api"
        else "^Process completion cannot be authenticated$")
    with pytest.raises(error, match=message) as observed:
        job.capture(1.0)
    assert type(observed.value) is error
    assert kernel.queries == 1 and job.members == {} and kernel.closed == []


@pytest.mark.parametrize("partial", [False, True], ids=["complete-lifetime", "partial-empty-lifetime"])
def test_capture_handle_lifetime_requires_explicit_cleanup(job_factory, partial: bool) -> None:
    rows = ([Snapshot(3, 2, (1, 2)), Snapshot(0, 0)] if partial
            else [Snapshot(2, 2, (1, 2))])
    job, kernel, clock = job_factory(rows)
    assert job.capture(1.0) is None
    known = dict(job.members)
    assert known == {1: _handle(1), 2: _handle(2)} and kernel.closed == []
    kernel.pending_once = set(known.values())
    clock.allow_sleep = True  # Existing wait path only, never capture's query policy.
    job.wait_members(1.0)
    assert kernel.waited == [(h, 0) for h in known.values()] * 2
    assert kernel.closed == [] and job.members == known and clock.sleeps == [0.005]
    job.close()
    assert job.handle is None and job.members == {}
    assert sorted(kernel.closed) == sorted([JOB_HANDLE, *known.values()])
    closed = list(kernel.closed)
    job.close()
    assert kernel.closed == closed
