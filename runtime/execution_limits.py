"""Hard execution limits for bounded multi-agent SEO workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass


class InvalidExecutionLimits(ValueError):
    """Raised when execution limits are unsafe or internally inconsistent."""


@dataclass(frozen=True)
class ExecutionLimits:
    """Per-run ceilings. A workflow graph never implies permission to exceed them."""

    max_nodes: int = 20
    max_llm_calls: int = 12
    max_parallel_agents: int = 3
    max_correction_attempts: int = 1
    max_workflow_depth: int = 3
    max_runtime_seconds: int = 900
    max_estimated_cost: float | None = None

    def __post_init__(self) -> None:
        integer_limits = {
            "max_nodes": self.max_nodes,
            "max_llm_calls": self.max_llm_calls,
            "max_parallel_agents": self.max_parallel_agents,
            "max_correction_attempts": self.max_correction_attempts,
            "max_workflow_depth": self.max_workflow_depth,
            "max_runtime_seconds": self.max_runtime_seconds,
        }
        for name, value in integer_limits.items():
            if not isinstance(value, int) or value < 0:
                raise InvalidExecutionLimits(f"{name} must be a non-negative integer")
        if self.max_nodes < 1:
            raise InvalidExecutionLimits("max_nodes must be at least 1")
        if self.max_llm_calls < 1:
            raise InvalidExecutionLimits("max_llm_calls must be at least 1")
        if self.max_parallel_agents < 1:
            raise InvalidExecutionLimits("max_parallel_agents must be at least 1")
        if self.max_workflow_depth < 1:
            raise InvalidExecutionLimits("max_workflow_depth must be at least 1")
        if self.max_runtime_seconds < 1:
            raise InvalidExecutionLimits("max_runtime_seconds must be at least 1")
        if self.max_estimated_cost is not None and self.max_estimated_cost < 0:
            raise InvalidExecutionLimits("max_estimated_cost cannot be negative")

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)
