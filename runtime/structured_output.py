"""Strict, schema-validated agent output with one bounded correction attempt."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _echo_output(
    agent_name: str,
    request: str,
    domain: str,
    skills: list[str],
    knowledge: list[str],
    prior_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Explicit synthetic output for deterministic offline execution, never a live finding."""
    evidence_refs = [
        str(item.get("source"))
        for prior in prior_outputs
        for item in prior.get("evidence", [])
        if isinstance(item, dict) and item.get("source")
    ]
    evidence_source = evidence_refs[0] if evidence_refs else "runtime_request"
    return {
        "output_id": f"synthetic-{re.sub(r'[^a-z0-9]+', '-', agent_name.lower()).strip('-')}",
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
                "id": f"synthetic-{re.sub(r'[^a-z0-9]+', '-', agent_name.lower()).strip('-')}-001",
                "severity": "Low",
                "finding": (
                    f"{agent_name} executed in synthetic offline mode for request: {request[:160]}"
                ),
                "affected_scope": domain or "Unspecified property",
                "evidence_refs": [evidence_source],
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
    }


class StructuredOutputService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.schemas = SchemaRegistry(repo_root)

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
        budget: RunBudget,
    ) -> StructuredOutputResult:
        if getattr(client, "provider", "") == "echo":
            output = _echo_output(
                agent_name, request, domain, skills, knowledge, prior_outputs
            )
            errors = self.schemas.errors("agent-output", output)
            return StructuredOutputResult(
                status="ok" if not errors else "failed",
                output=output if not errors else None,
                errors=errors,
                attempts=0,
                response=None,
                synthetic=True,
            )

        schema = self.schemas.load("agent-output")
        instruction = LLMMessage(
            role="system",
            content=(
                "Return only one JSON object that validates against this JSON Schema. "
                "Do not wrap prose in a fake schema shell. Do not invent evidence, URLs, metrics, "
                "completion claims, or provider results. Every factual numeric or URL claim must "
                "also appear in material_claims with valid evidence_refs.\n\n"
                + json.dumps(schema, separators=(",", ":"))
            ),
        )
        active_messages = [*messages, instruction]
        attempts = 0
        last_response: LLMResponse | None = None
        errors: list[str] = []

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
                output.setdefault("material_claims", [])
                output.setdefault("skills_used", skills)
                output.setdefault("knowledge_used", knowledge)
                output.setdefault("execution_state", "COMPLETE")
                errors = self.schemas.errors("agent-output", output)
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
