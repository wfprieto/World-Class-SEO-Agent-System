"""Structural, fail-closed validation for mandatory quality workflow steps."""

from __future__ import annotations

import re
from typing import Any

import yaml

COVERAGE_TARGETS = ("runtime", "seoctl", "integrations", "adapters")


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate YAML key: {key}", key_node.start_mark
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _jobs(workflow: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        payload = yaml.load(workflow, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return [], [f"CI workflow YAML is invalid: {exc}"]
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
        return [], ["CI workflow must contain a jobs mapping"]
    jobs = [job for job in payload["jobs"].values() if isinstance(job, dict)]
    return jobs, []


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    value = job.get("steps", [])
    return [step for step in value if isinstance(step, dict)] if isinstance(value, list) else []


def _checkout_errors(jobs: list[dict[str, Any]]) -> list[str]:
    steps = [step for job in jobs for step in _steps(job)]
    checkouts = [
        step
        for step in steps
        if isinstance(step.get("uses"), str)
        and str(step["uses"]).startswith("actions/checkout@")
    ]
    errors = [] if checkouts else ["CI requires at least one pinned actions/checkout step"]
    for step in checkouts:
        reference = str(step["uses"]).split("@", 1)[1]
        settings = step.get("with", {})
        depth = settings.get("fetch-depth") if isinstance(settings, dict) else None
        if not re.fullmatch(r"[0-9a-f]{40}", reference):
            errors.append("every actions/checkout step must use an immutable 40-character SHA")
        if not (
            depth == "0"
            or (isinstance(depth, int) and not isinstance(depth, bool) and depth == 0)
        ):
            errors.append("every actions/checkout step must set fetch-depth: 0")
    return errors


def _is_exact_step(step: dict[str, Any], command: str) -> bool:
    return set(step) <= {"name", "run"} and step.get("run") == command


def _quality_step_errors(
    jobs: list[dict[str, Any]], coverage: str, risk: str
) -> list[str]:
    errors: list[str] = []
    locations = [
        (job_index, step_index, step)
        for job_index, job in enumerate(jobs)
        for step_index, step in enumerate(_steps(job))
    ]
    coverage_at = [
        (job, index) for job, index, step in locations if _is_exact_step(step, coverage)
    ]
    risk_at = [(job, index) for job, index, step in locations if _is_exact_step(step, risk)]
    if len(coverage_at) != 1:
        errors.append("CI coverage command must be one exact dedicated unmasked step")
    if len(risk_at) != 1:
        errors.append("CI risk coverage command must be one exact dedicated unmasked step")
    if len(coverage_at) == len(risk_at) == 1 and not (
        coverage_at[0][0] == risk_at[0][0] and coverage_at[0][1] < risk_at[0][1]
    ):
        errors.append("CI coverage must precede risk validation in the same job")
    if coverage_at and any(key in jobs[coverage_at[0][0]] for key in ("if", "continue-on-error")):
        errors.append("CI quality job must not be conditional or continue on error")
    return errors


def workflow_errors(workflow: str, coverage_floor: float) -> list[str]:
    """Reject shallow checkout and any masked or weakened quality command."""
    coverage = (
        "pytest -q "
        + " ".join(f"--cov={target}" for target in COVERAGE_TARGETS)
        + " --cov-report=term-missing --cov-report=xml:outputs/coverage.xml"
        + " --cov-report=json:outputs/coverage.json "
        + f"--cov-fail-under={coverage_floor:g} --junitxml=outputs/pytest-quality.xml"
    )
    risk = "python scripts/validate_risk_coverage.py outputs/coverage.json"
    jobs, errors = _jobs(workflow)
    errors += _checkout_errors(jobs)
    errors += _quality_step_errors(jobs, coverage, risk)
    return errors
