#!/usr/bin/env python3
"""Fail-closed validation for repository governance and captured provider state."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADVISORY_URL = (
    "https://github.com/wfprieto/World-Class-SEO-Agent-System/security/advisories/new"
)
CERTIFICATION_NEEDS = {
    "validation_matrix",
    "validate",
    "quality_security_release",
    "clean_wheel_install",
    "phase0_rollback_certification",
    "phase_rollback_certification",
}


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


def local_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    support = (root / "SUPPORT.md").read_text(encoding="utf-8")
    config = _load_yaml(root / ".github/ISSUE_TEMPLATE/config.yml")
    workflow = _load_yaml(root / ".github/workflows/validate.yml")
    contract = _load_json(root / "governance/github-controls.json")

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

    names: dict[str, str] = {}
    for path in sorted((root / ".github/ISSUE_TEMPLATE").glob("*.yml")):
        document = _load_yaml(path)
        name = document.get("name")
        if isinstance(name, str) and name in names:
            errors.append(f"duplicate issue-template name {name!r}: {names[name]} and {path.name}")
        elif isinstance(name, str):
            names[name] = path.name

    ruleset = contract.get("ruleset", {})
    expected = {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": True,
        "require_last_push_approval": True,
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
    jobs = workflow.get("jobs", {})
    matching = [job for job in jobs.values() if job.get("name") == "repository-certification"]
    if len(matching) != 1:
        errors.append("exactly one repository-certification workflow job is required")
    else:
        job = matching[0]
        needs = job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        if set(needs) != CERTIFICATION_NEEDS:
            errors.append("repository-certification must depend on every canonical certification job")
        run_text = "\n".join(
            str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)
        )
        for need in CERTIFICATION_NEEDS - {"validation_matrix"}:
            if f"needs.{need}.result" not in run_text:
                errors.append(f"repository-certification does not enforce {need} result")
    return errors


def provider_errors(snapshot_path: Path, root: Path = ROOT) -> list[str]:
    snapshot = _load_json(snapshot_path)
    contract = _load_json(root / "governance/github-controls.json")
    errors: list[str] = []
    if snapshot.get("repository") != contract.get("repository"):
        errors.append("provider snapshot repository does not match the contract")
    for key in ("default_branch", "private_vulnerability_reporting", "discussions", "vulnerability_alerts"):
        if snapshot.get(key) != contract.get(key):
            errors.append(f"provider setting {key} does not match the contract")
    observed = snapshot.get("ruleset")
    expected = contract.get("ruleset")
    if not isinstance(expected, dict):
        return ["governance contract is missing the normalized ruleset"]
    if not isinstance(observed, dict):
        errors.append("provider snapshot is missing the normalized ruleset")
    else:
        for key, value in expected.items():
            if observed.get(key) != value:
                errors.append(f"provider ruleset.{key} does not match the contract")
    captured_at = snapshot.get("captured_at")
    if not isinstance(captured_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured_at):
        errors.append("provider snapshot requires a UTC captured_at timestamp")
    if snapshot.get("authenticated") is not True:
        errors.append("provider snapshot must attest authenticated capture")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-snapshot", type=Path)
    args = parser.parse_args()
    errors = local_errors()
    if args.provider_snapshot:
        errors.extend(provider_errors(args.provider_snapshot))
    if errors:
        print(json.dumps({"result": "FAIL", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"result": "PASS", "provider_verified": bool(args.provider_snapshot)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
