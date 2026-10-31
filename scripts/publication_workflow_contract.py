"""Sealed publication profiles plus independent command/privilege/source invariants."""

from __future__ import annotations

import hashlib
import json
import re
from importlib import import_module
from typing import Any

import yaml

source = import_module(f"{__package__ + '.' if __package__ else ''}workflow_quality_contract")
PROFILE_SHA = {
    "prepare": "4fc11cc5915dbd6e82cae3ac2a25311ac9a337e88bd88ef6e8834ad8f6cc64c4",
    "release": "dd486e5b0e543a997b6ffe35ad250e38a0e699f8cd886447571efe3997b9e91a",
}
SELECTION = ('--prepare-run-id "$PUB_PREPARE_RUN" --artifact-id "$PUB_ARTIFACT" '
             '--evidence-pr "$PUB_EVIDENCE_PR" --owner-comment-id "$PUB_OWNER_COMMENT"')
SELECTION_ENV = {"GH_TOKEN": "${{ github.token }}", "PUB_PREPARE_RUN": "${{ inputs.prepare_run_id }}",
                 "PUBLICATION_LIVE_READ_TOKEN": "${{ secrets.PUBLICATION_LIVE_READ_TOKEN }}",
                 "PUBLICATION_BENCHMARK_READ_TOKEN": "${{ secrets.PUBLICATION_BENCHMARK_READ_TOKEN }}",
                 "PUBLICATION_REPRODUCTION_READ_TOKEN": "${{ secrets.PUBLICATION_REPRODUCTION_READ_TOKEN }}",
                 "PUB_ARTIFACT": "${{ inputs.artifact_id }}", "PUB_EVIDENCE_PR": "${{ inputs.evidence_pr }}",
                 "PUB_OWNER_COMMENT": "${{ inputs.owner_comment_id }}"}
PERMISSIONS = {
    "build": {"contents": "read", "actions": "read"},
    "attest": {"contents": "read", "actions": "read", "id-token": "write", "attestations": "write"},
    "authorize": {"contents": "read", "actions": "read", "pull-requests": "read", "attestations": "read"},
    "publish": {"contents": "write", "actions": "read", "pull-requests": "read", "attestations": "read"},
    "complete": {"contents": "read", "actions": "read", "pull-requests": "read",
                 "attestations": "write", "id-token": "write"},
}
NEEDS = {"build": None, "attest": "build", "authorize": None, "publish": "authorize", "complete": "publish"}


def _document(workflow: str) -> dict[str, Any]:
    if re.search(r"(?m)^(?:on|'on'|\"on\")\s*:", workflow) is None:
        raise ValueError("Publication requires a literal on trigger mapping")
    result = yaml.load(workflow, Loader=source.UniqueKeyLoader)
    if not isinstance(result, dict):
        raise ValueError("Publication workflow must be a mapping")
    if True in result and "on" not in result:
        result["on"] = result.pop(True)
    if any(not isinstance(key, str) for key in result):
        raise ValueError("Publication workflow keys must be unambiguous strings")
    return result


def profile_digest(workflow: str) -> str:
    document = _document(workflow)
    for job in document.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if (isinstance(step, dict) and source._is_checkout(step)
                    and isinstance(step.get("with"), dict) and step["with"].get("fetch-depth") == "0"):
                step["with"]["fetch-depth"] = 0
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _commands(role: str) -> list[dict[str, Any]]:
    if role == "build":
        return [{"name": "Install locked preparation toolchain", "run": "python -B -m pip install -r requirements-dev.txt"},
                {"name": "Prepare exact source candidate once",
                 "env": {"GH_TOKEN": "${{ github.token }}", "PUB_CI_RUN": "${{ inputs.ci_run_id }}"},
                 "run": 'python -B -m scripts.publication_cli prepare --ci-run-id "$PUB_CI_RUN" --out "$RUNNER_TEMP/publication-build"'}]
    if role == "attest":
        return [{"name": "Authenticate internal prepared byte handoff",
                 "env": {"GH_TOKEN": "${{ github.token }}", "PUB_BUILD_ARTIFACT": "${{ needs.build.outputs.artifact_id }}",
                         "PUB_BUILD_SHA256": "${{ needs.build.outputs.archive_sha256 }}"},
                 "run": 'python -B -m scripts.publication_cli verify-build --artifact-id "$PUB_BUILD_ARTIFACT" --archive-sha256 "$PUB_BUILD_SHA256" --out "$RUNNER_TEMP/publication-candidate"'}]
    names = {"authorize": "Authenticate exact publication authorization",
             "publish": "Publish only approved prepared bytes", "complete": "Observe actual publication completion"}
    command = "observe" if role == "complete" else role
    suffix = ' --out "$RUNNER_TEMP/publication-completion"' if role == "complete" else ""
    return [{"name": names[role], "env": SELECTION_ENV,
             "run": f"python -B -m scripts.publication_cli {command} {SELECTION}{suffix}"}]


def _role_errors(role: str, job: dict[str, Any]) -> list[str]:
    errors = []
    if job.get("permissions") != PERMISSIONS[role] or job.get("needs") != NEEDS[role]:
        errors.append(f"Publication {role} privilege/dependency profile must remain exact")
    if set(job) & {"if", "continue-on-error", "container", "services", "defaults", "environment"}:
        errors.append(f"Publication {role} cannot mask, redirect or condition its authority")
    commands = [step for step in source._steps(job) if "run" in step
                and step != source.TRUSTED_PYTHON_STEP and not source._is_source_gate(step, source.RELEASE_REF)]
    if commands != _commands(role):
        errors.append(f"Publication {role} critical commands/arguments/environment must remain exact")
    if any(not re.fullmatch(r"actions/(checkout|setup-python|attest|upload-artifact)@[0-9a-f]{40}",
                            str(step["uses"])) for step in source._steps(job) if "uses" in step):
        errors.append(f"Publication {role} requires only immutable canonical action identities")
    return errors


def publication_workflow_errors(workflow: str, *, kind: str) -> list[str]:
    if kind not in PROFILE_SHA:
        return ["Unknown publication workflow profile"]
    try:
        document = _document(workflow)
        actual = profile_digest(workflow)
    except (ValueError, TypeError, AttributeError, yaml.YAMLError):
        return ["Publication workflow is malformed or ambiguous"]
    roles = ("build", "attest") if kind == "prepare" else ("authorize", "publish", "complete")
    jobs, errors = source._jobs(workflow)
    errors = list(errors)
    if set(jobs) != set(roles):
        errors.append("Publication workflow must contain its exact stage roles")
    if document.get("permissions") != {"contents": "read"}:
        errors.append("Publication global permissions must remain read-only")
    trigger = document.get("on")
    if not isinstance(trigger, dict) or set(trigger) != {"workflow_dispatch"}:
        errors.append("Publication accepts only explicit manual dispatch, never a tag/push/PR trigger")
    errors += source._canonical_job_errors(jobs, roles)
    errors += source._checkout_errors(jobs, source.RELEASE_REF, set(roles))
    errors += source._source_integrity_errors(jobs, source.RELEASE_REF, set(roles))
    for role in roles:
        if role in jobs:
            errors += _role_errors(role, jobs[role])
    if actual != PROFILE_SHA[kind]:
        errors.append("Publication complete workflow must equal its reviewed finite contract")
    return errors
