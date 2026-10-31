"""Immutable source evidence and authenticated canonical CI receipts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__:
    from scripts.remediation_contracts import (
        CI_RUN_PATTERN,
        REQUIRED_CI_JOBS,
    )
else:
    from remediation_contracts import (
        CI_RUN_PATTERN,
        REQUIRED_CI_JOBS,
    )


def _evidence_errors(
    evidence: dict[str, Any],
    verified_commit: str | None,
    root: Path,
    label: str,
    *,
    allow_ancestor: bool = False,
    require_unchanged: bool = True,
    authenticate_ci: bool = False,
) -> list[str]:
    errors: list[str] = []
    evidence_class = str(evidence.get("class", ""))
    reference = str(evidence.get("ref", ""))
    evidence_commit = str(evidence.get("commit", ""))
    commit_is_valid = evidence_commit == verified_commit
    if allow_ancestor and evidence_commit and verified_commit and (root / ".git").exists():
        try:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", evidence_commit, verified_commit],
                cwd=root,
                check=True,
                capture_output=True,
                timeout=20,
            )
            commit_is_valid = True
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            commit_is_valid = False
    if not commit_is_valid:
        errors.append(f"{label} evidence is not bound to verified_commit or an immutable ancestor")
    if evidence_class in {"SOURCE", "AUTOMATED"}:
        errors.extend(
            _source_evidence_errors(
                evidence,
                verified_commit,
                root,
                label,
                allow_ancestor=allow_ancestor,
                require_unchanged=require_unchanged,
            )
        )
    if evidence_class == "CI":
        errors.extend(
            _ci_evidence_errors(
                evidence,
                verified_commit,
                label,
                allow_ancestor=allow_ancestor,
                authenticate_ci=authenticate_ci,
            )
        )
    if evidence.get("status") not in {"OBSERVED", "PASS"}:
        errors.append(f"{label} evidence {reference} is not passing")
    return errors


def _source_evidence_errors(
    evidence: dict[str, Any],
    verified_commit: str | None,
    root: Path,
    label: str,
    *,
    allow_ancestor: bool,
    require_unchanged: bool,
) -> list[str]:
    errors: list[str] = []
    evidence_commit = str(evidence.get("commit", ""))
    reference = str(evidence.get("ref", ""))
    source_path = reference.split("::", 1)[0]
    expected_digest = evidence.get("sha256")
    content: bytes | None = None
    content_commit = evidence_commit if allow_ancestor else verified_commit
    if (root / ".git").exists() and content_commit:
        try:
            content = subprocess.check_output(
                ["git", "show", f"{content_commit}:{source_path}"],
                cwd=root,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            content = None
    elif (root / source_path).is_file():
        content = (root / source_path).read_bytes()
    if content is None:
        errors.append(f"{label} evidence does not exist at verified_commit: {reference}")
    elif not expected_digest or hashlib.sha256(content).hexdigest() != expected_digest:
        errors.append(f"{label} evidence digest is not immutable: {reference}")
    if (
        allow_ancestor
        and require_unchanged
        and (root / ".git").exists()
        and verified_commit
        and expected_digest
    ):
        errors.extend(
            _ancestor_freshness_errors(
                root, str(verified_commit), source_path, str(expected_digest), label, reference
            )
        )
    return errors


def _ancestor_freshness_errors(
    root: Path,
    verified_commit: str,
    source_path: str,
    expected_digest: str,
    label: str,
    reference: str,
) -> list[str]:
    errors: list[str] = []
    try:
        verified_content = subprocess.check_output(
            ["git", "show", f"{verified_commit}:{source_path}"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        verified_content = None
    if verified_content is None or hashlib.sha256(verified_content).hexdigest() != expected_digest:
        errors.append(f"{label} ancestor evidence changed before verified_commit: {reference}")
    return errors


def _ci_evidence_errors(
    evidence: dict[str, Any],
    verified_commit: str | None,
    label: str,
    *,
    allow_ancestor: bool,
    authenticate_ci: bool,
) -> list[str]:
    errors: list[str] = []
    evidence_commit = str(evidence.get("commit", ""))
    reference = str(evidence.get("ref", ""))
    provenance = evidence.get("provenance", {})
    if not CI_RUN_PATTERN.fullmatch(reference):
        errors.append(f"{label} CI evidence is not a canonical repository run: {reference}")
    expected = {
        "repository": "wfprieto/World-Class-SEO-Agent-System",
        "workflow": "Validate repository",
        "conclusion": "success",
    }
    for key, value in expected.items():
        if provenance.get(key) != value:
            errors.append(f"{label} CI provenance {key} is not authenticated")
    expected_head_sha = evidence_commit if allow_ancestor else verified_commit
    if provenance.get("head_sha") != expected_head_sha:
        errors.append(f"{label} CI provenance head_sha is not the bound evidence commit")
    if allow_ancestor and evidence_commit != verified_commit:
        errors.append(f"{label} CI evidence must certify the exact verified_commit")
    jobs = provenance.get("jobs", [])
    if not isinstance(jobs, list) or not jobs or any(not str(job).strip() for job in jobs):
        errors.append(f"{label} CI provenance has no successful job inventory")
    if authenticate_ci:
        errors.extend(_github_ci_errors(reference, provenance, label))
    return errors


def _github_ci_errors(reference: str, provenance: dict[str, Any], label: str) -> list[str]:
    """Authenticate a GitHub Actions receipt when running inside canonical CI."""
    if not CI_RUN_PATTERN.fullmatch(reference):
        return []
    run_id = reference.rsplit("/", 1)[-1]
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        run_request = urllib.request.Request(
            f"https://api.github.com/repos/wfprieto/World-Class-SEO-Agent-System/actions/runs/{run_id}",
            headers=headers,
        )
        jobs_request = urllib.request.Request(
            f"https://api.github.com/repos/wfprieto/World-Class-SEO-Agent-System/actions/runs/{run_id}/jobs?per_page=100",
            headers=headers,
        )
        with urllib.request.urlopen(run_request, timeout=20) as response:
            run = json.load(response)
        with urllib.request.urlopen(jobs_request, timeout=20) as response:
            jobs_payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return [f"{label} GitHub CI receipt could not be authenticated: {exc}"]
    errors: list[str] = []
    observed = {
        "repository": run.get("repository", {}).get("full_name"),
        "workflow": run.get("name"),
        "head_sha": run.get("head_sha"),
        "conclusion": run.get("conclusion"),
    }
    for key, expected in observed.items():
        if provenance.get(key) != expected:
            errors.append(f"{label} GitHub API disagrees with CI provenance {key}")
    successful_jobs = {
        str(item.get("name"))
        for item in jobs_payload.get("jobs", [])
        if item.get("conclusion") == "success"
    }
    required = next((names for marker, names in REQUIRED_CI_JOBS.items() if marker in label), set())
    for required_name in required:
        if required_name == "validate":
            if "validate" not in successful_jobs:
                errors.append(f"{label} GitHub run lacks successful validate aggregate job")
        elif required_name not in successful_jobs:
            errors.append(f"{label} GitHub run lacks successful job {required_name}")
    return errors
