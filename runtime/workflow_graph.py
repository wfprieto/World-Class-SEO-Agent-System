"""Executable DAG definitions for coordinated SEO agent workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from runtime.routing import RouteResult
from runtime.state import SessionState


class WorkflowGraphError(ValueError):
    """Raised when a workflow graph is invalid or unsafe to execute."""


@dataclass(frozen=True)
class WorkflowNode:
    id: str
    agent: str
    depends_on: tuple[str, ...] = ()
    required: bool = True
    role: str = "specialist"
    condition: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowGraph:
    id: str
    nodes: list[WorkflowNode] = field(default_factory=list)
    deliverable_node_id: str = ""

    def validate(self, *, max_nodes: int, max_depth: int) -> None:
        if not self.nodes:
            raise WorkflowGraphError("workflow graph has no nodes")
        if len(self.nodes) > max_nodes:
            raise WorkflowGraphError(
                f"workflow graph has {len(self.nodes)} nodes; max_nodes={max_nodes}"
            )
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise WorkflowGraphError("workflow graph contains duplicate node ids")
        known = set(ids)
        if not self.deliverable_node_id:
            raise WorkflowGraphError("workflow graph has no explicit deliverable node")
        if self.deliverable_node_id not in known:
            raise WorkflowGraphError(
                f"deliverable node {self.deliverable_node_id!r} does not exist"
            )
        for node in self.nodes:
            unknown = set(node.depends_on) - known
            if unknown:
                raise WorkflowGraphError(
                    f"node {node.id} has unknown dependencies: {sorted(unknown)}"
                )
            if node.id in node.depends_on:
                raise WorkflowGraphError(f"node {node.id} depends on itself")

        depths: dict[str, int] = {}
        visiting: set[str] = set()

        def depth(node_id: str) -> int:
            if node_id in depths:
                return depths[node_id]
            if node_id in visiting:
                raise WorkflowGraphError("workflow graph contains a cycle")
            visiting.add(node_id)
            node = next(item for item in self.nodes if item.id == node_id)
            value = 1 + max((depth(dep) for dep in node.depends_on), default=0)
            visiting.remove(node_id)
            depths[node_id] = value
            return value

        graph_depth = max(depth(node.id) for node in self.nodes)
        if graph_depth > max_depth:
            raise WorkflowGraphError(
                f"workflow depth {graph_depth} exceeds max_workflow_depth={max_depth}"
            )

        downstream: dict[str, set[str]] = {node.id: set() for node in self.nodes}
        for node in self.nodes:
            for dependency in node.depends_on:
                downstream[dependency].add(node.id)
        if downstream[self.deliverable_node_id]:
            raise WorkflowGraphError("deliverable node must be terminal")

    def levels(self) -> list[list[WorkflowNode]]:
        """Topological levels. Nodes inside one level may run concurrently."""
        remaining = {node.id: node for node in self.nodes}
        completed: set[str] = set()
        levels: list[list[WorkflowNode]] = []
        while remaining:
            ready = [
                node
                for node in remaining.values()
                if set(node.depends_on).issubset(completed)
            ]
            if not ready:
                raise WorkflowGraphError("workflow graph contains a cycle")
            ready.sort(key=lambda item: item.id)
            levels.append(ready)
            for node in ready:
                completed.add(node.id)
                remaining.pop(node.id)
        return levels

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "deliverable_node_id": self.deliverable_node_id,
            "nodes": [node.to_dict() for node in self.nodes],
        }


def _slug(agent: str) -> str:
    return (
        agent.lower()
        .replace(" / ", "-")
        .replace("&", "and")
        .replace(" ", "-")
        .replace("/", "-")
    )


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _vertical_agents(session: SessionState) -> list[str]:
    value = session.business_context.business_type.lower()
    agents: list[str] = []
    if any(token in value for token in ("ecommerce", "e-commerce", "commerce", "retail")):
        agents.append("SEO E-commerce Agent")
    if any(token in value for token in ("local", "location", "service-area")):
        agents.append("Local SEO Agent")
    if any(token in value for token in ("international", "multilingual", "global")):
        agents.append("International & Multilingual SEO Agent")
    return agents[:2]


def build_workflow_graph(route: RouteResult, session: SessionState) -> WorkflowGraph:
    """Build the smallest complete graph for the routed deliverable."""
    if route.workflow == "workflows/full-audit-workflow.md":
        vertical = _vertical_agents(session)
        fixed = [
            "SEO Technical Agent",
            "SEO Copywriter/Content Agent",
            "SEO Information Architecture Agent",
            "SEO Accessibility Agent",
            "GEO / AIO Optimization Agent",
            "Negative SEO & Security Agent",
        ]
        optional_slots = vertical or ["SEO CRO Agent", "Competitive Intelligence Agent"]
        specialists = _dedupe([*fixed, *optional_slots])[:8]
        specialist_nodes = [
            WorkflowNode(
                id=f"specialist-{index:02d}-{_slug(agent)}",
                agent=agent,
                role="specialist",
            )
            for index, agent in enumerate(specialists, start=1)
        ]
        dependencies = tuple(node.id for node in specialist_nodes)
        lead = WorkflowNode(
            id="lead-synthesis",
            agent="SEO Full Audit/Analyst Agent",
            depends_on=dependencies,
            role="lead",
        )
        scrum = WorkflowNode(
            id="scrummaster-challenge",
            agent="SEO Scrummaster Agent",
            depends_on=(lead.id,),
            role="governance",
        )
        strategy = WorkflowNode(
            id="strategic-roadmap",
            agent="Senior SEO Strategist Agent",
            depends_on=(scrum.id,),
            role="strategy",
        )
        report = WorkflowNode(
            id="stakeholder-report",
            agent="SEO Output Report Agent",
            depends_on=(strategy.id,),
            role="report",
        )
        return WorkflowGraph(
            id="full-audit-v2",
            nodes=[*specialist_nodes, lead, scrum, strategy, report],
            deliverable_node_id=report.id,
        )

    support = [
        agent
        for agent in route.supporting_agents
        if agent
        not in {
            route.lead_agent,
            "SEO Scrummaster Agent",
            "Senior SEO Strategist Agent",
            "SEO Output Report Agent",
        }
    ]
    support = _dedupe(support)[:6]
    support_nodes = [
        WorkflowNode(
            id=f"support-{index:02d}-{_slug(agent)}",
            agent=agent,
            role="support",
        )
        for index, agent in enumerate(support, start=1)
    ]
    lead = WorkflowNode(
        id="lead-deliverable",
        agent=route.lead_agent,
        depends_on=tuple(node.id for node in support_nodes),
        role="lead",
    )
    nodes: list[WorkflowNode] = [*support_nodes, lead]
    final_dependency = lead.id

    if "SEO Scrummaster Agent" in route.supporting_agents or route.confidence == "Low":
        scrum = WorkflowNode(
            id="scrummaster-challenge",
            agent="SEO Scrummaster Agent",
            depends_on=(lead.id,),
            role="governance",
        )
        nodes.append(scrum)
        final_dependency = scrum.id

    if route.lead_agent == "Senior SEO Strategist Agent":
        final_dependency = lead.id
    elif "Senior SEO Strategist Agent" in route.supporting_agents:
        strategy = WorkflowNode(
            id="strategic-synthesis",
            agent="Senior SEO Strategist Agent",
            depends_on=(final_dependency,),
            role="strategy",
        )
        nodes.append(strategy)
        final_dependency = strategy.id

    if route.lead_agent != "SEO Output Report Agent":
        report = WorkflowNode(
            id="stakeholder-report",
            agent="SEO Output Report Agent",
            depends_on=(final_dependency,),
            required=False,
            role="report",
        )
        nodes.append(report)
        final_dependency = report.id

    return WorkflowGraph(
        id=f"routed-{_slug(route.lead_agent)}-v2",
        nodes=nodes,
        deliverable_node_id=final_dependency,
    )
