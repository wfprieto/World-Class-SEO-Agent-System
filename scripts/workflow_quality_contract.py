"""Structural, fail-closed validation for mandatory quality workflow steps."""

from __future__ import annotations

import re
from typing import Any

import yaml

COVERAGE_TARGETS = ("runtime", "seoctl", "integrations", "adapters")
CANDIDATE_REF = "${{ github.event.pull_request.head.sha || github.sha }}"
RELEASE_REF = "${{ github.sha }}"
DANGEROUS_ENV_EXACT = {
    "BASH_ENV",
    "COMSPEC",
    "ENV",
    "GITHUB_ENV",
    "GITHUB_PATH",
    "IFS",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "PATH",
    "PATHEXT",
    "SHELL",
    "SHELLOPTS",
    "VIRTUAL_ENV",
}
DANGEROUS_ENV_PREFIXES = ("COVERAGE_", "DYLD_", "PIP_", "PYTEST_", "PYTHON")
APPROVED_RUNNERS = {"ubuntu-latest", "windows-latest"}
MATRIX_RUNNER = "${{ matrix.os }}"
SOURCE_GATE_PREFIX = "python scripts/validate_source_integrity.py --expected-sha "


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
    defaults = payload.get("defaults", {})
    run_defaults = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    errors = []
    if isinstance(run_defaults, dict) and set(run_defaults) & {"shell", "working-directory"}:
        errors.append("CI workflow must not inherit shell or working-directory defaults")
    dangerous_env = _dangerous_env_keys(payload)
    if dangerous_env:
        errors.append(
            "CI workflow must not inherit execution-altering environment variables: "
            + ", ".join(dangerous_env)
        )
    jobs = [job for job in payload["jobs"].values() if isinstance(job, dict)]
    return jobs, errors


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    value = job.get("steps", [])
    return [step for step in value if isinstance(step, dict)] if isinstance(value, list) else []


def _dangerous_env_keys(owner: dict[str, Any]) -> list[str]:
    env = owner.get("env", {})
    if not isinstance(env, dict):
        return ["<invalid-env-mapping>"] if env is not None else []
    dangerous = []
    for key in env:
        normalized = str(key).upper()
        if normalized in DANGEROUS_ENV_EXACT or normalized.startswith(
            DANGEROUS_ENV_PREFIXES
        ):
            dangerous.append(str(key))
    return sorted(dangerous, key=str.casefold)


def _dangerous_container_env_keys(job: dict[str, Any]) -> list[str]:
    container = job.get("container", {})
    return _dangerous_env_keys(container) if isinstance(container, dict) else []


def _source_gate_command(expected_ref: str) -> str:
    return SOURCE_GATE_PREFIX + expected_ref


def _is_source_gate(step: dict[str, Any], expected_ref: str) -> bool:
    return set(step) <= {"name", "run"} and step.get("run") == _source_gate_command(
        expected_ref
    )


def _approved_runner(job: dict[str, Any]) -> bool:
    runner = job.get("runs-on")
    if isinstance(runner, str) and runner in APPROVED_RUNNERS:
        return True
    if runner != MATRIX_RUNNER:
        return False
    strategy = job.get("strategy", {})
    matrix = strategy.get("matrix", {}) if isinstance(strategy, dict) else {}
    operating_systems = matrix.get("os") if isinstance(matrix, dict) else None
    return operating_systems == ["windows-latest", "ubuntu-latest"]


def _job_source_profile_errors(job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _approved_runner(job):
        errors.append("checkout jobs must use an approved GitHub-hosted runner")
    if "container" in job or "services" in job:
        errors.append("checkout jobs must not use containers or services")
    dangerous_env = _dangerous_env_keys(job) + _dangerous_container_env_keys(job)
    if dangerous_env:
        errors.append(
            "checkout jobs must not inherit execution-altering environment variables: "
            + ", ".join(dangerous_env)
        )
    return errors


def _is_evidence_boundary(step: dict[str, Any]) -> bool:
    action = step.get("uses")
    return isinstance(step.get("run"), str) or (
        isinstance(action, str) and action.casefold().startswith("actions/attest@")
    )


def _poisons_command_channel(step: dict[str, Any]) -> bool:
    command = step.get("run")
    normalized = command.casefold() if isinstance(command, str) else ""
    return "github_env" in normalized or "github_path" in normalized


def _replaces_candidate_source(step: dict[str, Any]) -> bool:
    command = step.get("run")
    normalized = command.casefold() if isinstance(command, str) else ""
    return "git revert --no-commit" in normalized or "scripts/rehearse_phase_rollback.py" in normalized


def _ordered_source_errors(steps: list[dict[str, Any]], expected_ref: str) -> list[str]:
    errors: list[str] = []
    source_replaced = False
    for index, step in enumerate(steps):
        if _poisons_command_channel(step):
            errors.append("workflow commands must not poison GITHUB_ENV or GITHUB_PATH")
        previous_is_gate = index > 0 and _is_source_gate(steps[index - 1], expected_ref)
        gate = _is_source_gate(step, expected_ref)
        if _is_evidence_boundary(step) and not gate and not source_replaced and not previous_is_gate:
            errors.append(
                "every repository command must immediately follow the exact source-integrity gate"
            )
        source_replaced = source_replaced or _replaces_candidate_source(step)
    return errors


def _source_integrity_errors(jobs: list[dict[str, Any]], expected_ref: str) -> list[str]:
    errors: list[str] = []
    for job in jobs:
        steps = _steps(job)
        if not any(_is_checkout(step) for step in steps):
            continue
        errors += _job_source_profile_errors(job)
        errors += _ordered_source_errors(steps, expected_ref)
    return errors


def _is_checkout(step: dict[str, Any]) -> bool:
    action = step.get("uses")
    return isinstance(action, str) and action.casefold().startswith("actions/checkout@")


def _checkout_step_errors(step: dict[str, Any], expected_ref: str) -> list[str]:
    errors: list[str] = []
    reference = str(step["uses"]).split("@", 1)[1]
    settings = step.get("with", {})
    depth = settings.get("fetch-depth") if isinstance(settings, dict) else None
    credentials = settings.get("persist-credentials") if isinstance(settings, dict) else None
    candidate_ref = settings.get("ref") if isinstance(settings, dict) else None
    if not str(step["uses"]).startswith("actions/checkout@"):
        errors.append("every checkout step must use canonical lowercase actions/checkout identity")
    if not re.fullmatch(r"[0-9a-f]{40}", reference):
        errors.append("every actions/checkout step must use an immutable 40-character SHA")
    if not (
        depth == "0"
        or (isinstance(depth, int) and not isinstance(depth, bool) and depth == 0)
    ):
        errors.append("every actions/checkout step must set fetch-depth: 0")
    if credentials not in {False, "false"}:
        errors.append("every actions/checkout step must set persist-credentials: false")
    if candidate_ref != expected_ref:
        errors.append("every actions/checkout step must check out the exact event commit")
    if not isinstance(settings, dict) or set(settings) != {
        "fetch-depth",
        "persist-credentials",
        "ref",
    }:
        errors.append("actions/checkout accepts only canonical source-integrity settings")
    return errors


def _checkout_errors(jobs: list[dict[str, Any]], expected_ref: str) -> list[str]:
    steps = [step for job in jobs for step in _steps(job)]
    checkouts = [
        step
        for step in steps
        if isinstance(step.get("uses"), str)
        and str(step["uses"]).casefold().startswith("actions/checkout@")
    ]
    errors = [] if checkouts else ["CI requires at least one pinned actions/checkout step"]
    for step in checkouts:
        errors.extend(_checkout_step_errors(step, expected_ref))
    return errors


def _is_exact_step(step: dict[str, Any], command: str) -> bool:
    return set(step) <= {"name", "run"} and step.get("run") == command


def _has_run_defaults(owner: dict[str, Any]) -> bool:
    defaults = owner.get("defaults", {})
    run_defaults = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    return isinstance(run_defaults, dict) and bool(
        set(run_defaults) & {"shell", "working-directory"}
    )


def _exact_locations(jobs: list[dict[str, Any]], command: str) -> list[tuple[int, int]]:
    return [
        (job_index, step_index)
        for job_index, job in enumerate(jobs)
        for step_index, step in enumerate(_steps(job))
        if _is_exact_step(step, command)
    ]


def _quality_step_errors(
    jobs: list[dict[str, Any]], coverage: str, risk: str
) -> list[str]:
    errors: list[str] = []
    coverage_at = _exact_locations(jobs, coverage)
    risk_at = _exact_locations(jobs, risk)
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
    if coverage_at and _has_run_defaults(jobs[coverage_at[0][0]]):
        errors.append("CI quality job must not inherit shell or working-directory defaults")
    if coverage_at:
        quality_job = jobs[coverage_at[0][0]]
        dangerous_env = _dangerous_env_keys(quality_job)
        if dangerous_env:
            errors.append(
                "CI quality job must not inherit execution-altering environment variables: "
                + ", ".join(dangerous_env)
            )
        if "container" in quality_job:
            errors.append("CI quality job must not use a container")
    return errors


def workflow_errors(
    workflow: str, coverage_floor: float, release_workflow: str | None = None
) -> list[str]:
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
    errors += _checkout_errors(jobs, CANDIDATE_REF)
    errors += _source_integrity_errors(jobs, CANDIDATE_REF)
    errors += _quality_step_errors(jobs, coverage, risk)
    if release_workflow is not None:
        release_jobs, release_errors = _jobs(release_workflow)
        errors += release_errors
        errors += _checkout_errors(release_jobs, RELEASE_REF)
        errors += _source_integrity_errors(release_jobs, RELEASE_REF)
    return errors
