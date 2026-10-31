"""Real local subprocesses prove bounded tree cleanup, without provider calls."""

from __future__ import annotations

import ctypes
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from scripts.publication_process import _linux_group_running
from scripts.publication_process_windows import WindowsJob
from scripts.publication_transport import run_bounded


def _running(pid: int) -> bool:
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() != 87:
                raise OSError("Synthetic descendant liveness could not be established")
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        status = Path(f"/proc/{pid}/stat")
        return not status.exists() or status.read_text().split(") ", 1)[1][0] != "Z"
    except ProcessLookupError:
        return False


def _cleanup(pid: int) -> None:
    """Only dispose a PID emitted by this test's own synthetic child."""
    if not _running(pid):
        return
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(1, False, pid)
        if handle:
            kernel.TerminateProcess(handle, 99)
            kernel.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGKILL)


def _parent(pid_file: Path, *, parent_delay: float, inherited: bool = True) -> str:
    redirect = "" if inherited else ",stdout=subprocess.DEVNULL"
    return ("import subprocess,sys,time;from pathlib import Path;"
            "child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(3)']"
            + redirect + ");Path(" + repr(str(pid_file)) + ").write_text(str(child.pid));"
            + f"time.sleep({parent_delay})")


def test_timeout_kills_inherited_stdout_descendant_when_parent_exited(tmp_path: Path) -> None:
    pid_file = tmp_path / "descendant.pid"
    start = time.monotonic()
    try:
        with pytest.raises(ValueError, match="boundary"):
            run_bounded([sys.executable, "-B", "-c", _parent(pid_file, parent_delay=0)],
                        limit=4, timeout=0.2)
        elapsed = time.monotonic() - start
        assert elapsed < 1.5, f"Inherited stdout defeated deadline: {elapsed:.2f} seconds"
        assert not _running(int(pid_file.read_text())), "Owned descendant survived timeout"
    finally:
        if pid_file.exists():
            _cleanup(int(pid_file.read_text()))


@pytest.mark.parametrize("parent_delay", [0, 3])
def test_timeout_kills_tree_with_inherited_output(tmp_path: Path, parent_delay: int) -> None:
    pid_file = tmp_path / "descendant.pid"
    start = time.monotonic()
    try:
        with pytest.raises(ValueError, match="boundary"):
            run_bounded([sys.executable, "-B", "-c", _parent(pid_file, parent_delay=parent_delay)],
                        limit=4, timeout=0.3)
        assert time.monotonic() - start < 1.5
        assert not _running(int(pid_file.read_text()))
    finally:
        if pid_file.exists():
            _cleanup(int(pid_file.read_text()))


@pytest.mark.parametrize("parent_delay", [0, 3])
def test_blocked_input_cannot_hold_tree_or_deadline(tmp_path: Path, parent_delay: int) -> None:
    pid_file = tmp_path / "descendant.pid"
    code = _parent(pid_file, parent_delay=parent_delay, inherited=False)
    start = time.monotonic()
    try:
        with pytest.raises(ValueError, match="boundary"):
            run_bounded([sys.executable, "-B", "-c", code], limit=4,
                        body=b"x" * 1048576, timeout=0.3)
        assert time.monotonic() - start < 1.5
        assert not _running(int(pid_file.read_text()))
    finally:
        if pid_file.exists():
            _cleanup(int(pid_file.read_text()))


def test_success_also_terminates_owned_descendants(tmp_path: Path) -> None:
    pid_file = tmp_path / "descendant.pid"
    start = time.monotonic()
    try:
        assert run_bounded([sys.executable, "-B", "-c", _parent(
            pid_file, parent_delay=0, inherited=False)], limit=4, timeout=0.3) == b""
        assert time.monotonic() - start < 1.5
        assert not _running(int(pid_file.read_text())), "Success abandoned an owned descendant"
    finally:
        if pid_file.exists():
            _cleanup(int(pid_file.read_text()))


def test_large_binary_input_roundtrips_without_handshake_loss() -> None:
    payload = bytes(range(256)) * 4096
    code = "import sys;data=sys.stdin.buffer.read();sys.stdout.buffer.write(data)"
    assert run_bounded([sys.executable, "-B", "-c", code], limit=len(payload),
                       body=payload, timeout=5) == payload


def test_closed_stdout_does_not_bypass_process_deadline() -> None:
    code = "import os,time;os.close(1);time.sleep(3)"
    start = time.monotonic()
    with pytest.raises(ValueError, match="boundary"):
        run_bounded([sys.executable, "-B", "-c", code], limit=4, timeout=0.2)
    assert time.monotonic() - start < 1.5


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True,
                                     pytest.param(10**400, id="huge-positive"),
                                     pytest.param(-(10**400), id="huge-negative")])
def test_invalid_deadlines_fail_before_launch(timeout: float, tmp_path: Path) -> None:
    marker = tmp_path / "never-ran"
    code = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('ran')"
    with pytest.raises(ValueError, match="boundaries"):
        run_bounded([sys.executable, "-B", "-c", code], limit=4, timeout=timeout)
    assert not marker.exists()


@pytest.mark.parametrize("limit", [0, -1, True])
def test_invalid_limits_fail_before_launch(limit: int, tmp_path: Path) -> None:
    marker = tmp_path / "never-ran"
    code = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('ran')"
    with pytest.raises(ValueError, match="boundaries"):
        run_bounded([sys.executable, "-B", "-c", code], limit=limit, timeout=1)
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Requires actual Windows JobObject")
def test_denied_assignment_never_launches_target_or_leaves_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "never-ran"
    pids: list[int] = []

    def deny(self: WindowsJob, pid: int) -> None:
        pids.append(pid)
        raise OSError("synthetic containment denial")

    monkeypatch.setattr(WindowsJob, "assign", deny)
    code = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('ran')"
    with pytest.raises(ValueError, match="boundary"):
        run_bounded([sys.executable, "-B", "-c", code], limit=4, timeout=1)
    assert len(pids) == 1 and not _running(pids[0])
    assert not marker.exists()


def test_nonzero_exit_is_sanitized_without_output() -> None:
    with pytest.raises(ValueError, match=r"exit 7\)"):
        run_bounded([sys.executable, "-B", "-c", "import sys;sys.exit(7)"], limit=4, timeout=1)


def test_empty_input_reaches_real_eof_without_handshake_bytes() -> None:
    code = "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"
    assert run_bounded([sys.executable, "-B", "-c", code], limit=1, body=b"", timeout=1) == b""


def test_launcher_cannot_import_source_shadowed_stdlib(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "shadow-ran"
    shadow = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('ran')"
    (tmp_path / "subprocess.py").write_text(shadow)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    assert run_bounded([sys.executable, "-B", "-c", "print('ok',end='')"],
                       cwd=tmp_path, limit=2, timeout=1) == b"ok"
    assert not marker.exists()


@pytest.mark.parametrize("failure", ["print('oversized')", "sys.exit(7)"])
def test_size_and_exit_failures_also_clean_up_descendants(tmp_path: Path, failure: str) -> None:
    pid_file = tmp_path / "descendant.pid"
    code = _parent(pid_file, parent_delay=0, inherited=False) + ";" + failure
    start = time.monotonic()
    try:
        with pytest.raises(ValueError):
            run_bounded([sys.executable, "-B", "-c", code], limit=4, timeout=0.5)
        assert time.monotonic() - start < 1.5
        assert not _running(int(pid_file.read_text()))
    finally:
        if pid_file.exists():
            _cleanup(int(pid_file.read_text()))


def test_nested_descendants_do_not_outlive_exited_target(tmp_path: Path) -> None:
    nested = tmp_path / "nested.pid"
    immediate = tmp_path / "immediate.pid"
    child_code = _parent(nested, parent_delay=3)
    code = ("import subprocess,sys,time;from pathlib import Path;"
            f"p=subprocess.Popen([sys.executable,'-B','-c',{child_code!r}]);"
            f"Path({str(immediate)!r}).write_text(str(p.pid))")
    start = time.monotonic()
    try:
        with pytest.raises(ValueError, match="boundary"):
            run_bounded([sys.executable, "-B", "-c", code], limit=4, timeout=0.5)
        assert time.monotonic() - start < 1.5
        assert not _running(int(immediate.read_text()))
        assert not _running(int(nested.read_text()))
    finally:
        for path in (immediate, nested):
            if path.exists():
                _cleanup(int(path.read_text()))


@pytest.mark.parametrize("state,expected", [("S", True), ("R", True), ("Z", False), ("X", False)])
def test_linux_group_inspection_distinguishes_running_and_dead_members(
    tmp_path: Path, state: str, expected: bool,
) -> None:
    member = tmp_path / "123"
    member.mkdir()
    (member / "stat").write_text(f"123 (name with ) spaces) {state} 1 456 456 0 0 0")
    assert _linux_group_running(456, time.monotonic() + 1, tmp_path) is expected
    assert not _linux_group_running(999, time.monotonic() + 1, tmp_path)


def test_input_size_limit_fails_before_launch(tmp_path: Path) -> None:
    marker = tmp_path / "never-ran"
    code = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('ran')"
    with pytest.raises(ValueError, match="boundaries"):
        run_bounded([sys.executable, "-B", "-c", code], limit=4,
                    body=b"x" * (4 * 1024 * 1024 + 1), timeout=1)
    assert not marker.exists()


def test_bounded_process_captures_eight_sequential_children(tmp_path: Path) -> None:
    """Real portable process control; no synthetic API/clock or fallback PID killer."""
    pid_file = tmp_path / "eight-sequential.pids"
    code = (
        "import os,subprocess,sys\nfrom pathlib import Path\n"
        f"log=Path({str(pid_file)!r})\n"
        "log.write_text(str(os.getpid())+'\\n',encoding='ascii')\n"
        "if os.name=='nt':\n"
        " with log.open('a',encoding='ascii') as h: h.write(str(os.getppid())+'\\n')\n"
        "for number in range(8):\n"
        " child=subprocess.Popen([sys.executable,'-B','-c','pass'])\n"
        " with log.open('a',encoding='ascii') as h: h.write(str(child.pid)+'\\n')\n"
        " if child.wait()!=0: raise SystemExit(1)\n"
        "sys.stdout.write('eight-done')\n"
    )
    assert run_bounded([sys.executable, "-B", "-c", code], limit=64, timeout=5) == b"eight-done"
    owned_pids = [int(value) for value in pid_file.read_text(encoding="ascii").splitlines()]
    # Target + eight sequential children; Windows also has the actual waiting launcher.
    assert len(owned_pids) == (10 if os.name == "nt" else 9)
    assert all(pid > 0 and not _running(pid) for pid in owned_pids)
    # This pre-fixture-cleanup proof never signals a possibly reused PID. Production
    # cleanup and the outer owned Job are responsible for failures; no manual kill.
