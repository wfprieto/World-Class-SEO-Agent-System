"""Per-run budget accounting for multi-agent workflow execution."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Any

from runtime.execution_limits import ExecutionLimits


class BudgetExceeded(RuntimeError):
    """Raised before an operation would exceed an approved run limit."""


def estimate_request_cost(client: Any, messages: list[Any]) -> float | None:
    """Read an operator-verified synchronous whole-call quote, including retries.

    No provider/model prices are invented. An absent quote is unknown, not free.
    The configured estimator must cover request size, output allowance and every
    transport attempt. Each correction obtains a new quote for its own messages.
    """
    estimator = getattr(client, "estimate_request_cost", None)
    if not callable(estimator):
        return None
    try:
        return estimator(messages)
    except Exception:
        raise BudgetExceeded("LLM cost estimate is unavailable; no call was authorized") from None


def _cost_total(current: float | None, estimate: float | None, ceiling: float | None) -> float | None:
    if estimate is None:
        if ceiling is not None:
            raise BudgetExceeded("LLM cost is unknown under an active monetary ceiling")
        return None
    if (isinstance(estimate, bool) or not isinstance(estimate, (int, float))
            or not math.isfinite(estimate) or estimate < 0):
        raise BudgetExceeded("LLM cost estimate must be a finite non-negative number")
    total = None if current is None else current + float(estimate)
    if total is not None and not math.isfinite(total):
        raise BudgetExceeded("Accumulated LLM cost estimate is not finite")
    if ceiling is not None and (total is None or total > ceiling):
        raise BudgetExceeded("LLM estimated cost exceeds the approved monetary ceiling")
    return total


@dataclass
class BudgetUsage:
    nodes_started: int = 0
    llm_calls: int = 0
    correction_calls: int = 0
    estimated_cost: float | None = 0.0


class RunBudget:
    """Single-use budget. It is created for one workflow and never reused."""

    def __init__(self, limits: ExecutionLimits) -> None:
        self.limits = limits
        self.usage = BudgetUsage()
        self.started = time.monotonic()

    def check_runtime(self) -> None:
        elapsed = time.monotonic() - self.started
        if elapsed > self.limits.max_runtime_seconds:
            raise BudgetExceeded(
                f"workflow runtime exceeded {self.limits.max_runtime_seconds} seconds"
            )

    def reserve_node(self) -> None:
        self.check_runtime()
        if self.usage.nodes_started + 1 > self.limits.max_nodes:
            raise BudgetExceeded(f"workflow exceeds max_nodes={self.limits.max_nodes}")
        self.usage.nodes_started += 1

    def reserve_llm_call(
        self, *, correction: bool = False, estimated_cost: float | None = None
    ) -> None:
        self.check_runtime()
        if self.usage.llm_calls + 1 > self.limits.max_llm_calls:
            raise BudgetExceeded(
                f"workflow exceeds max_llm_calls={self.limits.max_llm_calls}"
            )
        if correction and self.usage.correction_calls + 1 > self.limits.max_correction_attempts:
            raise BudgetExceeded(
                "workflow exceeds max_correction_attempts="
                f"{self.limits.max_correction_attempts}"
            )
        next_cost = _cost_total(
            self.usage.estimated_cost, estimated_cost, self.limits.max_estimated_cost
        )
        self.usage.llm_calls += 1
        if correction:
            self.usage.correction_calls += 1
        self.usage.estimated_cost = next_cost

    def reserve_model_call(
        self, client: Any, messages: list[Any], *, correction: bool = False
    ) -> None:
        self.reserve_llm_call(
            correction=correction, estimated_cost=estimate_request_cost(client, messages)
        )

    def snapshot(self) -> dict[str, object]:
        self.check_runtime()
        return {
            "limits": self.limits.to_dict(),
            "usage": asdict(self.usage),
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
        }
