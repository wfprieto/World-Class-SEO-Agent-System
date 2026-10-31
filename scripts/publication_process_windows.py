"""Documented Win32 job containment and nonblocking byte pipes (Python 3.11+)."""

from __future__ import annotations

import ctypes as c
import sys
import time
from functools import cache


class _Limits(c.Structure):
    _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64),
                ("flags", c.c_uint32), ("minimum", c.c_size_t), ("maximum", c.c_size_t),
                ("active_limit", c.c_uint32), ("affinity", c.c_size_t),
                ("priority", c.c_uint32), ("scheduling", c.c_uint32)]


class _Extended(c.Structure):
    _fields_ = [("basic", _Limits), ("io", c.c_uint64 * 6),
                ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
                ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]


class _Accounting(c.Structure):
    _fields_ = [("times", c.c_int64 * 4), ("faults", c.c_uint32),
                ("total", c.c_uint32), ("active", c.c_uint32), ("terminated", c.c_uint32)]


@cache
def _kernel() -> c.CDLL:
    kernel: c.CDLL
    if sys.platform == "win32":
        kernel = c.WinDLL("kernel32", use_last_error=True)
    else:
        raise OSError("Windows process containment is unavailable")
    signatures = {
        "CreateJobObjectW": ([c.c_void_p, c.c_wchar_p], c.c_void_p),
        "OpenProcess": ([c.c_uint32, c.c_int, c.c_uint32], c.c_void_p),
        "CloseHandle": ([c.c_void_p], c.c_int),
        "WaitForSingleObject": ([c.c_void_p, c.c_uint32], c.c_uint32),
        "AssignProcessToJobObject": ([c.c_void_p, c.c_void_p], c.c_int),
        "TerminateJobObject": ([c.c_void_p, c.c_uint32], c.c_int),
        "SetInformationJobObject": ([c.c_void_p, c.c_int, c.c_void_p, c.c_uint32], c.c_int),
        "QueryInformationJobObject": (
            [c.c_void_p, c.c_int, c.c_void_p, c.c_uint32, c.c_void_p], c.c_int),
        "SetNamedPipeHandleState": (
            [c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p], c.c_int),
        "ReadFile": ([c.c_void_p, c.c_void_p, c.c_uint32, c.c_void_p, c.c_void_p], c.c_int),
        "WriteFile": ([c.c_void_p, c.c_void_p, c.c_uint32, c.c_void_p, c.c_void_p], c.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


class WindowsJob:
    """A noninheritable unnamed job; never permit command launch before assignment."""

    def __init__(self) -> None:
        self.kernel = _kernel()
        self.handle: int | None = self.kernel.CreateJobObjectW(None, None)
        self.assigned = False
        self.members: dict[int, int] = {}
        if not self.handle:
            raise OSError("Process containment is unavailable")
        limits = _Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
        if not self.kernel.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            self.close()
            raise OSError("Process containment limits could not be established")

    def assign(self, pid: int) -> None:
        process = self.kernel.OpenProcess(0x101, False, pid)  # SET_QUOTA | TERMINATE.
        if not process:
            raise OSError("Waiting launcher is unavailable")
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise OSError("Process containment assignment was denied")
            self.assigned = True
        finally:
            self.kernel.CloseHandle(process)

    def terminate(self, deadline: float) -> None:
        # At cleanup only: no surviving member can start another runnable child.
        limits = _Extended()
        limits.basic.flags, limits.basic.active_limit = 0x2008, 1
        if not self.kernel.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            raise OSError("Process creation could not be closed before cleanup")
        self.capture(deadline)
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise OSError("Process tree termination failed")
        while True:
            state = _Accounting()
            if not self.kernel.QueryInformationJobObject(
                    self.handle, 1, c.byref(state), c.sizeof(state), None):
                raise OSError("Process tree cleanup could not be verified")
            if state.active == 0:
                self.wait_members(deadline)
                return
            self.capture(deadline)
            if time.monotonic() >= deadline:
                raise TimeoutError("Process tree cleanup exceeded its deadline")
            time.sleep(0.005)

    def close(self) -> None:
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)  # Kill-on-close is also the failure backstop.
            self.handle = None
        for handle in self.members.values():
            self.kernel.CloseHandle(handle)
        self.members.clear()

    def capture(self, deadline: float) -> None:
        # Retain real process handles: active=0 accounting can precede process signaling.
        buffer = c.create_string_buffer(8 + 4096 * c.sizeof(c.c_size_t))
        if not self.kernel.QueryInformationJobObject(
                self.handle, 3, buffer, c.sizeof(buffer), None):
            raise OSError("Complete process membership is unavailable")
        assigned, count = (c.c_uint32.from_buffer(buffer, offset).value for offset in (0, 4))
        if assigned != count or count > 4096 or len(self.members) + count > 8192:
            raise ValueError("Process membership exceeds its finite boundary")
        for pid in (c.c_size_t * count).from_buffer(buffer, 8):
            if time.monotonic() >= deadline:
                raise TimeoutError("Process membership capture exceeded deadline")
            if pid not in self.members:
                handle = self.kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only.
                if handle:
                    self.members[pid] = handle
                elif sys.platform != "win32" or c.get_last_error() != 87:
                    raise OSError("Process completion cannot be authenticated")

    def wait_members(self, deadline: float) -> None:
        while True:
            pending = False
            for handle in self.members.values():
                status = self.kernel.WaitForSingleObject(handle, 0)
                if status not in {0, 258}:
                    raise OSError("Process completion wait failed")
                pending |= status == 258
                if time.monotonic() >= deadline:
                    raise TimeoutError("Process completion exceeded cleanup deadline")
            if not pending:
                return
            time.sleep(0.005)


class WindowsPipe:
    """Immediate ReadFile/WriteFile avoids Python 3.11 CRT EAGAIN differences."""

    def __init__(self, fd: int) -> None:
        self.handle: int
        self.kernel: c.CDLL
        if sys.platform == "win32":
            import msvcrt

            self.handle = msvcrt.get_osfhandle(fd)
        else:
            raise OSError("Windows nonblocking process pipes are unavailable")

        self.kernel = _kernel()
        mode = c.c_uint32(1)  # PIPE_NOWAIT applies to anonymous pipes too.
        if not self.kernel.SetNamedPipeHandleState(self.handle, c.byref(mode), None, None):
            raise OSError("Nonblocking process pipe is unavailable")

    def read(self, size: int) -> bytes | None:
        buffer = c.create_string_buffer(size)
        count = c.c_uint32()
        if self.kernel.ReadFile(self.handle, buffer, size, c.byref(count), None):
            return buffer.raw[:count.value]
        error: int
        if sys.platform == "win32":
            error = c.get_last_error()
        else:
            raise OSError("Windows process pipes are unavailable")
        if error == 232:  # ERROR_NO_DATA: connected byte pipe currently empty.
            return None
        if error == 109:  # ERROR_BROKEN_PIPE: every owned writer has closed.
            return b""
        raise OSError("Process output pipe failed")

    def write(self, data: bytes) -> int:
        count = c.c_uint32()
        if not self.kernel.WriteFile(self.handle, data, len(data), c.byref(count), None):
            raise OSError("Process input pipe failed")
        return count.value  # Byte pipes can accept a partial write or zero bytes.
