"""Finite, threadless process I/O with owned Windows jobs or POSIX groups."""

from __future__ import annotations

import math
import os
import re
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from scripts.publication_credentials import child_environment
from scripts.publication_policy import MAX_API_BYTES, MAX_MEMBER_BYTES, REPOSITORY
from scripts.publication_process_windows import WindowsJob, WindowsPipe

CLEANUP_SECONDS = 2.0
_LAUNCHER = (
    "import os,subprocess,sys;"
    "gate=os.read(0,1);"
    "sys.exit(125) if gate!=b'\\x01' else None;"
    "sys.exit(subprocess.Popen(sys.argv[1:],stdin=sys.stdin.buffer).wait())"
)
_UPLOAD_ENDPOINT = re.compile(
    re.escape(f"https://uploads.github.com/repos/{REPOSITORY}/releases/")
    + r"[1-9][0-9]*/assets\?name=[A-Za-z0-9][A-Za-z0-9_.-]{0,255}"
)


class Pipe(Protocol):
    def read(self, size: int) -> bytes | None: ...
    def write(self, data: bytes) -> int: ...


class PosixPipe:
    def __init__(self, fd: int) -> None:
        self.fd = fd
        if sys.platform == "win32":
            raise OSError("POSIX process pipes are unavailable on Windows")
        else:
            os.set_blocking(fd, False)

    def read(self, size: int) -> bytes | None:
        try:
            return os.read(self.fd, size)
        except BlockingIOError:
            return None

    def write(self, data: bytes) -> int:
        try:
            return os.write(self.fd, data)
        except BlockingIOError:
            return 0


def _exchange(process: subprocess.Popen[bytes], body: bytes, limit: int,
              deadline: float, job: WindowsJob | None) -> tuple[bytes, int]:
    if process.stdout is None or process.stdin is None:
        raise ValueError("Process pipes are unavailable")
    adapter = WindowsPipe if os.name == "nt" else PosixPipe
    reader, writer = adapter(process.stdout.fileno()), adapter(process.stdin.fileno())
    result = bytearray()
    offset, ended = 0, False
    while time.monotonic() < deadline:
        if job is not None:
            job.capture(deadline)
        if offset < len(body):
            offset += writer.write(body[offset:offset + 65536])
        elif not process.stdin.closed:
            process.stdin.close()
        if not ended:
            block = reader.read(min(65536, limit + 1 - len(result)))
            if block is not None:
                ended = not block
                result.extend(block)
                if len(result) > limit:
                    raise ValueError("Provider response exceeded its byte limit")
        code = process.poll()
        if ended and offset == len(body) and code is not None:
            return bytes(result), code
        time.sleep(min(0.005, max(0, deadline - time.monotonic())))
    raise TimeoutError("Provider operation exceeded its deadline")


def _cleanup(process: subprocess.Popen[bytes], job: WindowsJob | None) -> None:
    deadline = time.monotonic() + CLEANUP_SECONDS
    try:
        if job is not None and job.assigned:
            job.terminate(deadline)
        elif sys.platform != "win32":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()  # Unassigned launcher has not received its launch byte.
    finally:
        if job is not None:
            job.close()
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
            if job is None:
                _wait_group(process.pid, deadline)
        finally:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()  # Unbuffered; no worker needs to be joined.


def _linux_group_running(group: int, deadline: float, proc: Path = Path("/proc")) -> bool:
    for entry in proc.iterdir():
        if time.monotonic() >= deadline:
            raise TimeoutError("Process group inspection exceeded cleanup deadline")
        if not entry.name.isdecimal():
            continue
        try:
            # comm can contain spaces or parentheses; fields begin after its last closing ') '.
            with (entry / "stat").open("rb") as stream:
                raw = stream.read(65537)
        except (FileNotFoundError, ProcessLookupError):
            continue
        fields = raw.rsplit(b") ", 1)[-1].split()
        if len(raw) > 65536 or len(fields) < 3:
            raise ValueError("Process cleanup metadata is malformed")
        if int(fields[2]) == group and fields[0] not in {b"Z", b"X"}:
            return True
    return False


def _wait_group(group: int, deadline: float) -> None:
    if sys.platform == "win32":
        raise OSError("POSIX process groups are unavailable")
    while True:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return
        if sys.platform == "linux" and not _linux_group_running(group, deadline):
            return  # Dead/zombie descendants cannot retain pipes or execute.
        if time.monotonic() >= deadline:
            raise TimeoutError("Process group did not quiesce before cleanup deadline")
        time.sleep(0.005)


def _input_limit(args: list[str], body: bytes) -> int:
    """A size allowance only: callers still own executable and role authority."""
    if (len(args) == 13 and args[1:4] == ["api", "--hostname", "github.com"]
            and isinstance(args[4], str) and _UPLOAD_ENDPOINT.fullmatch(args[4]) is not None
            and args[5:12] == ["--method", "POST", "--input", "-", "--header",
                              "Content-Type: application/octet-stream", "--header"]
            and args[12] == f"Content-Length: {len(body)}" and bool(body)):
        return MAX_MEMBER_BYTES
    return MAX_API_BYTES


def _arguments(args: list[str], limit: int, body: bytes | None, timeout: float) -> None:
    if (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1
            or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
            or timeout <= 0 or timeout > sys.float_info.max or not math.isfinite(timeout)
            or (body is not None and (not isinstance(body, bytes)
                                     or len(body) > _input_limit(args, body)))):
        raise ValueError("Provider command has invalid finite time/size boundaries")
    if os.name not in {"nt", "posix"}:
        raise ValueError("Process-tree containment is unavailable on this platform")


def bounded_process(args: list[str], *, limit: int, cwd: Path | None,
                    body: bytes | None, timeout: float, github_token: str | None = None) -> bytes:
    _arguments(args, limit, body, timeout)
    deadline = time.monotonic() + timeout
    job: WindowsJob | None = None
    process: subprocess.Popen[bytes] | None = None
    try:
        job = WindowsJob() if os.name == "nt" else None
        command = ([sys.executable, "-I", "-S", "-u", "-B", "-c", _LAUNCHER, *args]
                   if job is not None else args)
        environment = child_environment(github_token)
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   bufsize=0, start_new_session=job is None)
        try:
            if job is not None:
                job.assign(process.pid)
            payload = (b"\x01" if job is not None else b"") + (body or b"")
            data, code = _exchange(process, payload, limit, deadline, job)
        finally:
            _cleanup(process, job)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
        raise ValueError("Provider command failed its time/size boundary") from None
    finally:
        if job is not None:
            job.close()
    if code:
        raise ValueError(f"Provider command failed closed (exit {code})")
    return data
