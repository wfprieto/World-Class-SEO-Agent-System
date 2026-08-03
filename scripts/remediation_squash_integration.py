"""Validate the explicit bridge from reviewed remediation history to a squash merge."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

RECEIPT_PATH = Path("evaluation/remediation/squash-integration-receipt.json")
SCHEMA_PATH = Path("schemas/squash-integration-receipt.schema.json")


@dataclass(frozen=True)
class SquashIntegration:
    """Authenticated local Git identities that preserve the reviewed source graph."""

    source_closure: str
    target_commit: str


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=root,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=20,
    ).strip()


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def _validated_payload(
    root: Path, payload: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        receipt = payload or json.loads((root / RECEIPT_PATH).read_text(encoding="utf-8"))
        schema = json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = [
            f"squash integration schema {'.'.join(map(str, item.absolute_path)) or '<root>'}: {item.message}"
            for item in Draft202012Validator(schema).iter_errors(receipt)
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, [f"squash integration receipt cannot be loaded: {exc}"]
    return (None, errors) if errors else (receipt, [])


def _resolved_identities(root: Path, receipt: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    source = receipt["source"]
    target = receipt["target"]
    tag = source["evidence_tag"]
    try:
        identities = {
            "tag_type": _git(root, "cat-file", "-t", tag["name"]),
            "tag_object": _git(root, "rev-parse", tag["name"]),
            "peeled": _git(root, "rev-parse", f"{tag['name']}^{{}}"),
            "source_tree": _git(root, "rev-parse", f"{source['closure_commit']}^{{tree}}"),
            "target_tree": _git(root, "rev-parse", f"{target['commit']}^{{tree}}"),
            "parents": _git(root, "rev-list", "--parents", "-n", "1", target["commit"]).split(),
        }
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {}, ["squash integration Git identities cannot be resolved"]
    return identities, []


def _binding_errors(
    root: Path, receipt: dict[str, Any], identities: dict[str, Any], baseline_commit: str
) -> list[str]:
    errors: list[str] = []
    source = receipt["source"]
    target = receipt["target"]
    tag = source["evidence_tag"]
    if (source["baseline_commit"], receipt["pull_request"]["provider_head_sha"]) != (
        baseline_commit, source["closure_commit"]
    ):
        errors.append("squash integration baseline or PR head binding is invalid")
    if identities["tag_type"] != "tag":
        errors.append("squash integration evidence tag must be annotated")
    if identities["tag_object"] != tag["object_sha"]:
        errors.append("squash integration evidence tag object does not match the receipt")
    if identities["peeled"] != source["closure_commit"] or identities["peeled"] != tag["peeled_commit"]:
        errors.append("squash integration evidence tag does not peel to the source closure")
    if identities["source_tree"] != source["tree_sha"]:
        errors.append("squash integration source tree does not match the receipt")
    if identities["target_tree"] != target["tree_sha"] or identities["target_tree"] != identities["source_tree"]:
        errors.append("squash integration target tree is not exactly source-equivalent")
    if target["parent_commit"] != baseline_commit:
        errors.append("squash integration recorded parent does not match the baseline")
    if identities["parents"] != [target["commit"], baseline_commit]:
        errors.append("squash integration target is not the single-parent baseline successor")
    if not _is_ancestor(root, target["commit"], "HEAD"):
        errors.append("squash integration target is not an ancestor of HEAD")
    return errors


def validate_squash_integration(
    root: Path,
    baseline_commit: str,
    *,
    payload: dict[str, Any] | None = None,
) -> tuple[SquashIntegration | None, list[str]]:
    """Return a trusted integration context only when every exact binding passes."""

    if not (root / RECEIPT_PATH).is_file() or not (root / SCHEMA_PATH).is_file():
        return None, []
    receipt, errors = _validated_payload(root, payload)
    if receipt is None:
        return None, errors
    identities, errors = _resolved_identities(root, receipt)
    if errors:
        return None, errors
    errors = _binding_errors(root, receipt, identities, baseline_commit)
    source = receipt["source"]
    target = receipt["target"]
    context = SquashIntegration(source["closure_commit"], target["commit"])
    return (None, errors) if errors else (context, [])


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    """Expose the bounded ancestry predicate to the canonical validator."""

    return _is_ancestor(root, ancestor, descendant)


def accepted_history_contains(root: Path, baseline: str, commit: str) -> tuple[bool, list[str]]:
    """Accept direct ancestry or the one validated squash-source graph."""

    if _is_ancestor(root, commit, "HEAD"):
        return True, []
    integration, errors = validate_squash_integration(root, baseline)
    return bool(integration and _is_ancestor(root, commit, integration.source_closure)), errors


def accepted_history_errors(root: Path, baseline: str, commit: str) -> list[str]:
    """Return a stable error list for a commit outside every authenticated history."""

    accepted, errors = accepted_history_contains(root, baseline, commit)
    if errors:
        return errors
    return [] if accepted else ["commit is outside HEAD and the authenticated squash source"]


def closure_history_head(root: Path, baseline: str, snapshot: str) -> str:
    """Resolve the historical closure tip or raise on an unauthenticated graph."""

    if _is_ancestor(root, snapshot, "HEAD"):
        return "HEAD"
    integration, errors = validate_squash_integration(root, baseline)
    if errors or integration is None:
        raise ValueError("; ".join(errors) or "authenticated squash source is unavailable")
    return integration.source_closure
