"""Strict, schema-validated agent output with one bounded correction attempt."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.evidence_binding import validate_evidence_binding
from runtime.llm import LLMClient, LLMMessage, LLMResponse
from runtime.run_budget import BudgetExceeded, RunBudget
from runtime.schema_registry import SchemaRegistry


@dataclass
class StructuredOutputResult:
    status: str
    output: dict[str, Any] | None
    errors: list[str]
    attempts: int
    response: LLMResponse | None
    synthetic: bool = False


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model response did not contain a JSON object")
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("agent output must be a JSON object")
    return parsed


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _echo_output(
    agent_name: str,
    request: str,
    domain: str,
    skills: list[str],
    knowledge: list[str],
    prior_outputs: list[dict[str, Any]],
    required_handoffs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Explicit synthetic output for deterministic offline execution, never a live finding."""
    prior_finding_ids = [
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
    slug = _slug(agent_name)
    return {
        "output_id": f"synthetic-{slug}",
        "agent": agent_name,
        "summary": (
            "Synthetic offline execution completed for workflow verification. "
            "This output proves orchestration and contracts, not a real SEO conclusion."
        ),
        "evidence": [
            {
                "source": evidence_source,
                "type": "synthetic_runtime_fixture",
                "date_checked": "1970-01-01",
                "notes": "Offline echo-mode evidence; no live website or provider was inspected.",
            }
        ],
        "confidence": "Low",
        "findings": [
            {
                "id": f"synthetic-{slug}-001",
                "severity": "Low",
                "finding": f"{agent_name} executed in synthetic offline mode for request: {request[:160]}",
                "affected_scope": domain or "Unspecified property",
                "evidence_refs": evidence_refs or [evidence_source],
            }
        ],
        "recommended_actions": [
            {
                "action": "Supply verified site evidence before making or implementing SEO recommendations.",
                "priority": "P2",
                "owner": agent_name,
                "success_metric": "Required evidence is available and a non-synthetic agent run validates the finding.",
            }
        ],
        "impact": "Validates workflow wiring without asserting ranking, traffic, revenue, or compliance impact.",
        "effort": "Low",
        "risks": ["Synthetic output must not be presented as a completed SEO audit."],
        "owner": agent_name,
        "dependencies": ["Verified first-party or direct technical evidence"],
        "acceptance_criteria": ["A live or supplied-evidence run replaces the synthetic output."],
        "verification": ["Validate this object against schemas/agent-output.schema.json."],
        "follow_up": "Run again when verified evidence is available.",
        "material_claims": [],
        "skills_used": skills,
        "knowledge_used": knowledge,
        "execution_state": "SYNTHETIC",
        "handoff_acknowledgements": _echo_handoff_acknowledgements(required_handoffs),
    }


def _echo_handoff_acknowledgements(
    required_handoffs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "handoff_id": handoff["handoff_id"],
            "disposition": "ACCEPTED" if handoff["evidence_refs"] else "CHALLENGED",
            "requested_action_addressed": handoff["requested_action"],
            "evidence_refs_addressed": handoff["evidence_refs"],
            "acceptance_criteria_addressed": handoff["acceptance_criteria"],
            "resolution_note": "Synthetic acknowledgement; not production evidence.",
        }
        for handoff in required_handoffs
    ]


class StructuredOutputService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.schemas = SchemaRegistry(repo_root)

    def _errors(
        self,
        output: dict[str, Any],
        *,
        expected_agent: str,
    ) -> list[str]:
        errors = self.schemas.errors("agent-output", output)
        if output.get("agent") != expected_agent:
            errors.append(
                f"agent identity mismatch: expected {expected_agent!r}, got {output.get('agent')!r}"
            )
        errors.extend(validate_evidence_binding(output))
        return errors

    def _complete_echo(
        self,
        *,
        agent_name: str,
        request: str,
        domain: str,
        skills: list[str],
        knowledge: list[str],
        prior_outputs: list[dict[str, Any]],
        required_handoffs: list[dict[str, Any]],
    ) -> StructuredOutputResult:
        output = _echo_output(
            agent_name,
            request,
            domain,
            skills,
            knowledge,
            prior_outputs,
            required_handoffs,
        )
        errors = self._errors(output, expected_agent=agent_name)
        return StructuredOutputResult(
            status="ok" if not errors else "failed",
            output=output if not errors else None,
            errors=errors,
            attempts=0,
            response=None,
            synthetic=True,
        )

    async def complete_agent_output(
        self,
        client: LLMClient,
        messages: list[LLMMessage],
        *,
        agent_name: str,
        request: str,
        domain: str,
        skills: list[str],
        knowledge: list[str],
        prior_outputs: list[dict[str, Any]],
        required_handoffs: list[dict[str, Any]],
        budget: RunBudget,
    ) -> StructuredOutputResult:
        if getattr(client, "provider", "") == "echo":
            return self._complete_echo(
                agent_name=agent_name,
                request=request,
                domain=domain,
                skills=skills,
                knowledge=knowledge,
                prior_outputs=prior_outputs,
                required_handoffs=required_handoffs,
            )

        schema = self.schemas.load("agent-output")
        instruction = LLMMessage(
            role="system",
            content=(
                f"You are {agent_name!r}. Return only one JSON object whose agent field is exactly "
                f"{agent_name!r} and that validates against this JSON Schema. Do not wrap prose in "
                "a fake schema shell. Do not invent evidence, URLs, metrics, completion claims, or "
                "provider results. Every factual numeric or URL claim must also appear in "
                "material_claims with valid evidence_refs. Downstream findings must explicitly "
                "reference or challenge the supplied dependency evidence.\n\n"
                + json.dumps(schema, separators=(",", ":"))
            ),
        )
        active_messages = [*messages, instruction]
        attempts = 0
        last_response: LLMResponse | None = None
        errors: list[str] = []
        output: dict[str, Any] | None = None

        for correction in range(budget.limits.max_correction_attempts + 1):
            try:
                budget.reserve_llm_call(correction=correction > 0)
            except BudgetExceeded as exc:
                return StructuredOutputResult(
                    status="blocked",
                    output=None,
                    errors=[str(exc)],
                    attempts=attempts,
                    response=last_response,
                )
            attempts += 1
            last_response = await client.complete(active_messages)
            try:
                output = _extract_json(last_response.content)
            except (ValueError, json.JSONDecodeError) as exc:
                errors = [str(exc)]
                output = None
            else:
                output.setdefault("output_id", f"{_slug(agent_name)}-output")
                output.setdefault("material_claims", [])
                output.setdefault("skills_used", skills)
                output.setdefault("knowledge_used", knowledge)
                output.setdefault("execution_state", "COMPLETE")
                errors = self._errors(output, expected_agent=agent_name)
                if not errors:
                    return StructuredOutputResult(
                        status="ok",
                        output=output,
                        errors=[],
                        attempts=attempts,
                        response=last_response,
                    )

            if correction >= budget.limits.max_correction_attempts:
                break
            active_messages = [
                *messages,
                instruction,
                LLMMessage(
                    role="user",
                    content=(
                        "Your previous output was invalid. Correct only the JSON object. "
                        "Validation errors:\n- " + "\n- ".join(errors[:20])
                    ),
                ),
            ]

        return StructuredOutputResult(
            status="failed",
            output=None,
            errors=errors or ["agent output validation failed"],
            attempts=attempts,
            response=last_response,
        )
