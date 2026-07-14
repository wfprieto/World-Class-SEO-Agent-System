from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "runtime/structured_output.py",
    '''    evidence_refs = [
        str(item.get("source"))
        for prior in prior_outputs
        for item in prior.get("evidence", [])
        if isinstance(item, dict) and item.get("source")
    ]
    evidence_source = evidence_refs[0] if evidence_refs else "runtime_request"
''',
    '''    prior_finding_ids = [
        str(item.get("id"))
        for prior in prior_outputs
        for item in prior.get("findings", [])
        if isinstance(item, dict) and item.get("id")
    ]
    prior_sources = [
        str(item.get("source"))
        for prior in prior_outputs
        for item in prior.get("evidence", [])
        if isinstance(item, dict) and item.get("source")
    ]
    evidence_refs = prior_finding_ids or prior_sources
    evidence_source = prior_sources[0] if prior_sources else "runtime_request"
''',
)

replace_once(
    "runtime/workflow_runner.py",
    '''            output_id = str(output.get("output_id") or output.get("agent") or node.id)
            # Consume every pending handoff addressed to this agent, including the initial
            # risk escalation and direct dependency handoffs.
            for pending in session.handoffs:
                if pending.status == "CREATED" and pending.to_agent == node.agent:
                    pending.consume(output_id)
''',
    '''            output_id = str(output.get("output_id") or output.get("agent") or node.id)
            referenced_evidence = {
                str(reference)
                for finding in output.get("findings", [])
                if isinstance(finding, dict)
                for reference in finding.get("evidence_refs", [])
            }
            referenced_evidence.update(
                str(item.get("id"))
                for item in output.get("evidence", [])
                if isinstance(item, dict) and item.get("id")
            )
            # A handoff is consumed only when the receiving output explicitly references
            # evidence carried by that exact handoff. Delivery to an agent identity alone
            # is not substantive consumption.
            for pending in session.handoffs:
                if pending.status != "CREATED" or pending.to_agent != node.agent:
                    continue
                if pending.evidence_refs and set(pending.evidence_refs).intersection(
                    referenced_evidence
                ):
                    pending.consume(output_id)
''',
)

replace_once(
    "runtime/workflow_runner.py",
    '''        final_node = next(
            (
                node.id
                for node in reversed(graph.nodes)
                if node.id in outputs_by_node
                and states.get(node.id) in {"COMPLETE", "SYNTHETIC"}
            ),
            None,
        )
        final_output = outputs_by_node.get(final_node) if final_node else None
''',
    '''        final_node = graph.deliverable_node_id
        final_output = (
            outputs_by_node.get(final_node)
            if states.get(final_node) in {"COMPLETE", "SYNTHETIC"}
            else None
        )
''',
)

replace_once(
    "runtime/workflow_runner.py",
    '''        if required_failures:
            workflow_status = "FAILED"
        elif optional_failures or required_tool_failures or conflicts or has_synthetic or unresolved_handoffs:
            workflow_status = "PARTIAL"
        else:
            workflow_status = "COMPLETE"
''',
    '''        deliverable_missing = final_output is None
        if required_failures or deliverable_missing:
            workflow_status = "FAILED"
        elif optional_failures or required_tool_failures or conflicts or has_synthetic or unresolved_handoffs:
            workflow_status = "PARTIAL"
        else:
            workflow_status = "COMPLETE"
''',
)
