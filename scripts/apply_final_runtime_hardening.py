from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:100]!r}")
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
            # Delivery to an agent identity is not substantive consumption. A handoff is
            # consumed only when the receiving output explicitly references evidence carried
            # by that exact handoff. Empty-evidence risk handoffs remain open for a decision.
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
    '''        required_failures = [
            node.id
            for node in graph.nodes
            if node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        optional_failures = [
            node.id
            for node in graph.nodes
            if not node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        has_synthetic = any(state == "SYNTHETIC" for state in states.values())
        unresolved_handoffs = [
            handoff for handoff in session.handoffs if handoff.status != "CONSUMED"
        ]
        if required_failures:
            workflow_status = "FAILED"
        elif optional_failures or required_tool_failures or conflicts or has_synthetic or unresolved_handoffs:
            workflow_status = "PARTIAL"
        else:
            workflow_status = "COMPLETE"
        session.workflow_status = workflow_status
        session.budget_usage = budget.snapshot()

        final_node = next(
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
    '''        required_failures = [
            node.id
            for node in graph.nodes
            if node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        optional_failures = [
            node.id
            for node in graph.nodes
            if not node.required and states.get(node.id) not in {"COMPLETE", "SYNTHETIC"}
        ]
        has_synthetic = any(state == "SYNTHETIC" for state in states.values())
        unresolved_handoffs = [
            handoff for handoff in session.handoffs if handoff.status != "CONSUMED"
        ]
        final_node = graph.deliverable_node_id
        final_output = (
            outputs_by_node.get(final_node)
            if states.get(final_node) in {"COMPLETE", "SYNTHETIC"}
            else None
        )
        if required_failures or final_output is None:
            workflow_status = "FAILED"
        elif optional_failures or required_tool_failures or conflicts or has_synthetic or unresolved_handoffs:
            workflow_status = "PARTIAL"
        else:
            workflow_status = "COMPLETE"
        session.workflow_status = workflow_status
        session.budget_usage = budget.snapshot()
''',
)

replace_once(
    "scripts/validate_release_artifacts.py",
    '''    if manifest.get("command_count", 0) < 1 or manifest.get("skill_count") != 84:
        failures.append("manifest command or skill inventory is invalid")
''',
    '''    catalog = json.loads(
        (root / "skills" / "skill-catalog.json").read_text(encoding="utf-8")
    )
    expected_skill_count = sum(
        len(row.get("skills", [])) for row in catalog.get("categories", [])
    )
    if manifest.get("command_count", 0) < 1:
        failures.append("manifest command inventory is invalid")
    if manifest.get("skill_count") != expected_skill_count:
        failures.append(
            "manifest skill inventory is invalid: "
            f"expected {expected_skill_count}, got {manifest.get('skill_count')}"
        )
''',
)

# Extend regression coverage for semantic handoff consumption and dynamic release inventory.
test_path = Path("tests/test_runtime_hardening.py")
test_text = test_path.read_text(encoding="utf-8")
appendix = '''\n\ndef test_release_validator_uses_canonical_skill_catalog() -> None:\n    source = Path("scripts/validate_release_artifacts.py").read_text(encoding="utf-8")\n    assert "skill-catalog.json" in source\n    assert "!= 84" not in source\n\n\ndef test_workflow_runner_does_not_auto_consume_by_agent_identity() -> None:\n    source = Path("runtime/workflow_runner.py").read_text(encoding="utf-8")\n    assert "referenced_evidence" in source\n    assert "pending.evidence_refs and" in source\n    assert "pending.status == \\\"CREATED\\\" and pending.to_agent == node.agent" not in source\n\n\ndef test_workflow_runner_uses_explicit_deliverable_node() -> None:\n    source = Path("runtime/workflow_runner.py").read_text(encoding="utf-8")\n    assert "final_node = graph.deliverable_node_id" in source\n    assert "for node in reversed(graph.nodes)" not in source\n'''
if "test_release_validator_uses_canonical_skill_catalog" not in test_text:
    test_path.write_text(test_text + appendix, encoding="utf-8")
