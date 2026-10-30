"""A logical HTTP operation deadline that shuts down its active sockets."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec('P')
T = TypeVar('T')
_ACTIVE: ContextVar[HttpDeadline | None] = ContextVar('http_deadline', default=None)


def validate_timeout(timeout: float) -> float:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('HTTP timeout must be finite and positive')
    return float(timeout)


def _close_socket(sock: Any) -> None:
    with suppress(OSError, AttributeError):
        sock.shutdown(2)  # SHUT_RDWR, without a second network implementation.
    with suppress(OSError):
        sock.close()


class HttpDeadline:
    def __init__(self, timeout: float) -> None:
        timeout = validate_timeout(timeout)
        self.expires = time.monotonic() + timeout
        self._lock = threading.Lock()
        self._sockets: list[Any] = []
        self._expired = False
        self.timer = threading.Timer(timeout, self._expire)
        self.timer.daemon = True

    def remaining(self) -> float:
        remaining = self.expires - time.monotonic()
        if remaining <= 0 or self._expired:
            raise TimeoutError('HTTP logical-operation deadline exceeded')
        return remaining

    def register(self, sock: Any) -> Any:
        with self._lock:
            if self._expired or time.monotonic() >= self.expires:
                _close_socket(sock)
                raise TimeoutError('HTTP logical-operation deadline exceeded')
            self._sockets.append(sock)
        return sock

    def _expire(self) -> None:
        with self._lock:
            self._expired = True
            sockets = list(self._sockets)
        for sock in sockets:
            _close_socket(sock)


def check_deadline() -> None:
    if (deadline := _ACTIVE.get()) is not None:
        deadline.remaining()


def register_socket(sock: Any) -> Any:
    deadline = _ACTIVE.get()
    return deadline.register(sock) if deadline is not None else sock


def remaining_timeout(timeout: float) -> float:
    timeout = validate_timeout(timeout)
    deadline = _ACTIVE.get()
    return min(timeout, deadline.remaining()) if deadline is not None else timeout


def request_deadline(function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def bounded(*args: P.args, **kwargs: P.kwargs) -> T:
        if _ACTIVE.get() is not None:
            check_deadline()
            return function(*args, **kwargs)
        owner = args[0]
        timeout = getattr(owner, 'timeout', getattr(owner, 'timeout_seconds', 30))
        deadline = HttpDeadline(float(timeout))
        token = _ACTIVE.set(deadline)
        deadline.timer.start()
        try:
            result = function(*args, **kwargs)
            deadline.remaining()
            return result
        except Exception:
            deadline.remaining()
            raise
        finally:
            deadline.timer.cancel()
            _ACTIVE.reset(token)
    return bounded
