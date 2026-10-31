#!/usr/bin/env python3
"""Fail-closed validation for repository governance and captured provider state."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADVISORY_URL = "https://github.com/wfprieto/World-Class-SEO-Agent-System/security/advisories/new"
CERTIFICATION_NEEDS = {
    "validation_matrix",
    "provider_authentication",
    "validate",
    "quality_security_release",
    "clean_wheel_install",
    "phase0_rollback_certification",
    "phase_rollback_certification",
}
PROVIDER_JOB_MARKERS = (
    "WCSEO_AUTHENTICATE_CI_RECEIPTS",
    "GITHUB_TOKEN",
    "capture_github_controls.py --ci-observable",
    "Reject provider-unverifiable fork pull requests",
    "head.repo.full_name != github.repository",
    "repository certification fails closed",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def _phase8_local_errors(contract: dict[str, Any], provider_job: object) -> list[str]:
    errors: list[str] = []
    expected_pull = {
        "number": 67,
        "base": "main",
        "head": "codex/resolve-open-issues-26-32",
        "allowed_states": ["OPEN", "CLOSED"],
    }
    if contract.get("phase8_pull_request") != expected_pull:
        errors.append("Phase 8 provider evidence must bind the exact remediation pull request")
    expected_permissions = {
        "contents": "read",
        "issues": "read",
        "pull-requests": "read",
    }
    if isinstance(provider_job, dict) and provider_job.get("permissions") != expected_permissions:
        errors.append(
            "provider-authentication permissions must be exact read-only contents/issues/pull-requests"
        )
    return errors


def _intake_errors(root: Path, security: str, support: str, config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if ADVISORY_URL not in security:
        errors.append("SECURITY.md must link directly to the private advisory form")
    contact_urls = {link.get("url") for link in config.get("contact_links", [])}
    if ADVISORY_URL not in contact_urls:
        errors.append("issue configuration must link directly to the private advisory form")
    support_form = root / ".github/ISSUE_TEMPLATE/support_request.yml"
    if not support_form.is_file() or "support_request.yml" not in support:
        errors.append("a documented repository-owned support request form is required")
    elif "credentials, private URLs, client data" not in support_form.read_text(encoding="utf-8"):
        errors.append("support form must require removal of sensitive data")
    if (root / ".github/ISSUE_TEMPLATE/bug_report.md").exists():
        errors.append("legacy duplicate bug_report.md must not weaken the issue form")

    return errors


def _workflow_reference_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for workflow_path in sorted((root / ".github/workflows").glob("*.yml")):
        workflow_text = workflow_path.read_text(encoding="utf-8")
        for reference in re.findall(r"\buses:\s*([^\s#]+)", workflow_text):
            if not re.fullmatch(r"[^/@\s]+/[^/@\s]+@[0-9a-f]{40}", reference):
                errors.append(f"{workflow_path.name} has mutable action reference {reference}")
        workflow_document = _load_yaml(workflow_path)
        for job in workflow_document.get("jobs", {}).values():
            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                reference = str(step.get("uses", ""))
                options = step.get("with", {})
                if not isinstance(options, dict):
                    options = {}
                if (
                    reference.startswith("actions/checkout@")
                    and options.get("persist-credentials") is not False
                ):
                    errors.append(
                        f"{workflow_path.name} checkout must set persist-credentials: false"
                    )

    return errors


def _template_name_errors(root: Path) -> list[str]:
    errors: list[str] = []
    names: dict[str, str] = {}
    for path in sorted((root / ".github/ISSUE_TEMPLATE").glob("*.yml")):
        document = _load_yaml(path)
        name = document.get("name")
        if isinstance(name, str) and name in names:
            errors.append(f"duplicate issue-template name {name!r}: {names[name]} and {path.name}")
        elif isinstance(name, str):
            names[name] = path.name
    return errors


def _contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ruleset = contract.get("ruleset", {})
    for service in (
        "private_vulnerability_reporting",
        "vulnerability_alerts",
        "dependabot_security_updates",
        "secret_scanning",
        "secret_scanning_push_protection",
    ):
        if contract.get(service) is not True:
            errors.append(f"governance contract must require {service}=true")
    expected = {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": True,
        "require_last_push_approval": False,
        "required_review_thread_resolution": True,
        "required_linear_history": True,
        "block_deletion": True,
        "block_non_fast_forward": True,
        "bypass_actor_count": 0,
    }
    for key, value in expected.items():
        if ruleset.get(key) != value:
            errors.append(f"governance contract must set ruleset.{key}={value!r}")
    checks = ruleset.get("required_status_checks", [])
    if [check.get("context") for check in checks] != ["repository-certification"]:
        errors.append("repository-certification must be the sole required status check")
    reviewer = contract.get("independent_reviewer", {})
    if reviewer.get("accountable_owner") != "Repository maintainer":
        errors.append("solo-maintainer governance requires the repository maintainer owner")
    if reviewer.get("due_phase") != "P8":
        errors.append("solo-maintainer governance decision must remain bound to Phase P8")
    if (reviewer.get("status"), reviewer.get("merge_availability")) != (
        "NOT_APPLICABLE_SOLO_MAINTAINER",
        "AVAILABLE_AFTER_REQUIRED_STATUS_CHECKS",
    ):
        errors.append("governance must bind truthful solo-maintainer status to required checks")
    return errors


def _workflow_trigger_errors(workflow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if workflow.get("permissions") != {"contents": "read"}:
        errors.append("validation workflow must retain least-privilege contents: read permission")
    triggers = workflow.get("on")
    if not isinstance(triggers, dict):
        # PyYAML 1.1 may parse the plain scalar `on` as boolean true.
        triggers = workflow.get("True")
    if not isinstance(triggers, dict):
        triggers = {}
    pull_request = triggers.get("pull_request")
    if pull_request not in (None, {}):
        errors.append("validation must run on every pull request without path filters")
    return errors


def _provider_job_errors(workflow: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    jobs = workflow.get("jobs", {})
    matrix_job = jobs.get("validation_matrix", {})
    matrix_text = json.dumps(matrix_job, sort_keys=True)
    if "GITHUB_TOKEN" in matrix_text or "capture_github_controls.py" in matrix_text:
        errors.append("runtime matrix must remain deterministic and provider-offline")
    provider_job = jobs.get("provider_authentication")
    if not isinstance(provider_job, dict) or provider_job.get("name") != "provider-authentication":
        errors.append("one centralized provider-authentication job is required")
    else:
        provider_text = json.dumps(provider_job, sort_keys=True)
        for required_text in PROVIDER_JOB_MARKERS:
            if required_text not in provider_text:
                errors.append(f"provider-authentication job is missing {required_text}")
    errors.extend(_phase8_local_errors(contract, provider_job))
    return errors


def _aggregate_errors(jobs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    aggregate = jobs.get("validate", {})
    aggregate_needs = aggregate.get("needs", []) if isinstance(aggregate, dict) else []
    if isinstance(aggregate_needs, str):
        aggregate_needs = [aggregate_needs]
    if set(aggregate_needs) != {"validation_matrix", "provider_authentication"}:
        errors.append("validate aggregate must require matrix and provider authentication")
    aggregate_text = json.dumps(aggregate, sort_keys=True)
    if "needs.provider_authentication.result" not in aggregate_text:
        errors.append("validate aggregate must enforce provider-authentication success")
    return errors


def _certification_errors(jobs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    matching = [job for job in jobs.values() if job.get("name") == "repository-certification"]
    if len(matching) != 1:
        errors.append("exactly one repository-certification workflow job is required")
    else:
        job = matching[0]
        needs = job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        if set(needs) != CERTIFICATION_NEEDS:
            errors.append(
                "repository-certification must depend on every canonical certification job"
            )
        run_text = "\n".join(
            str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)
        )
        for need in CERTIFICATION_NEEDS - {"validation_matrix"}:
            if f"needs.{need}.result" not in run_text:
                errors.append(f"repository-certification does not enforce {need} result")
    return errors


def local_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    support = (root / "SUPPORT.md").read_text(encoding="utf-8")
    config = _load_yaml(root / ".github/ISSUE_TEMPLATE/config.yml")
    workflow = _load_yaml(root / ".github/workflows/validate.yml")
    contract = _load_json(root / "governance/github-controls.json")
    errors.extend(_intake_errors(root, security, support, config))
    errors.extend(_workflow_reference_errors(root))
    errors.extend(_template_name_errors(root))
    errors.extend(_contract_errors(contract))
    errors.extend(_workflow_trigger_errors(workflow))
    errors.extend(_provider_job_errors(workflow, contract))
    jobs = workflow.get("jobs", {})
    errors.extend(_aggregate_errors(jobs))
    errors.extend(_certification_errors(jobs))
    return errors
