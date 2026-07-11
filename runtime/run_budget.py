"""Per-run budget accounting for multi-agent workflow execution."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from runtime.execution_limits import ExecutionLimits


class BudgetExceeded(RuntimeError):
    """Raised before an operation would exceed an approved run limit."""


@dataclass
class BudgetUsage:
    nodes_started: int = 0
    llm_calls: int = 0
    correction_calls: int = 0
    estimated_cost: float = 0.0


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

    def reserve_llm_call(self, *, correction: bool = False, estimated_cost: float = 0.0) -> None:
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
        next_cost = self.usage.estimated_cost + max(float(estimated_cost), 0.0)
        ceiling = self.limits.max_estimated_cost
        if ceiling is not None and next_cost > ceiling:
            raise BudgetExceeded(
                f"workflow estimated cost {next_cost:.4f} exceeds ceiling {ceiling:.4f}"
            )
        self.usage.llm_calls += 1
        if correction:
            self.usage.correction_calls += 1
        self.usage.estimated_cost = next_cost

    def snapshot(self) -> dict[str, object]:
        self.check_runtime()
        return {
            "limits": self.limits.to_dict(),
            "usage": asdict(self.usage),
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
        }
