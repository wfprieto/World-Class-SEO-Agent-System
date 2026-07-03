"""Base contracts for SEO tool adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AdapterNotConfigured(RuntimeError):
    """Raised when credentials or source files are missing."""


@dataclass
class AdapterResult:
    source: str
    status: str
    data: Any
    warnings: list[str]


class SEOAdapter(Protocol):
    name: str

    def fetch(self, **kwargs: Any) -> AdapterResult:
        """Fetch or parse data and return a normalized adapter result."""

