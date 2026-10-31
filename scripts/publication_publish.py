"""Publish only reauthenticated approved bytes; never rebuild, replace or resume."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_authorize import AuthorizedCandidate, authorize_candidate, canonical
from scripts.publication_context import workflow_context
from scripts.publication_remote import (
    items,
    observed_release,
    observed_tag,
    unused_destination,
    upload_asset,
)
from scripts.publication_subject import JsonObject, integer_value, object_value, string_value
from scripts.publication_transport import GitHubCLI


def _refresh(root: Path, api: GitHubCLI, baseline: AuthorizedCandidate) -> AuthorizedCandidate:
    workflow_context(root, api, policy.PUBLICATION_WORKFLOW, "publish")
    fresh = authorize_candidate(root, api, **baseline.selection(), now=datetime.now(UTC))
    if canonical(fresh.binding()) != canonical(baseline.binding()):
        raise ValueError("Publication authorization changed at an irreversible boundary")
    fresh.temporal_proof.assert_current(datetime.now(UTC))
    return fresh


def _draft(api: GitHubCLI, release_id: int, tag: str, uploaded: dict[str, int]) -> None:
    record = object_value(api.json(f"/repos/{policy.REPOSITORY}/releases/{release_id}"), "draft")
    if (record.get("id") != release_id or record.get("tag_name") != tag
            or record.get("draft") is not True or record.get("published_at") is not None):
        raise ValueError("Fresh draft identity/state changed; automatic recovery is prohibited")
    assets = items(api, f"/repos/{policy.REPOSITORY}/releases/{release_id}/assets")
    actual = {string_value(row.get("name"), "draft asset"): integer_value(row.get("id"), "asset ID")
              for row in assets}
    if actual != uploaded or len(actual) != len(assets):
        raise ValueError("Draft asset inventory changed; no replacement or clobber is permitted")


def _new_draft(root: Path, api: GitHubCLI, candidate: AuthorizedCandidate) -> int:
    subject = candidate.bundle.subject
    tag = string_value(subject["planned_tag"], "planned tag")
    if any(row.get("tag_name") == tag for row in items(api, f"/repos/{policy.REPOSITORY}/releases")):
        raise ValueError("Unexpected existing release; automatic resume is prohibited")
    _refresh(root, api, candidate)
    result = object_value(api.write(f"/repos/{policy.REPOSITORY}/releases", {
        "tag_name": tag, "target_commitish": subject["candidate_commit"], "name": tag,
        "body": "Prepared bytes authenticated against publication-subject.json; completion pending.",
        "draft": True, "prerelease": False,
    }), "new draft")
    release_id = integer_value(result.get("id"), "new release ID")
    _draft(api, release_id, tag, {})
    return release_id


def _upload(api: GitHubCLI, release_id: int, name: str, data: bytes) -> int:
    record = upload_asset(api, release_id, name, data)
    if (record.get("name") != name or record.get("size") != len(data)
            or record.get("state") != "uploaded"
            or record.get("digest") != "sha256:" + hashlib.sha256(data).hexdigest()):
        raise ValueError("Uploaded asset acknowledgement does not match its approved bytes")
    return integer_value(record.get("id"), "uploaded asset ID")


def publish_candidate(root: Path, api: GitHubCLI, *, selection: dict[str, int]) -> JsonObject:
    workflow_context(root, api, policy.PUBLICATION_WORKFLOW, "publish")
    candidate = authorize_candidate(root, api, **selection, now=datetime.now(UTC))
    subject = candidate.bundle.subject
    tag = string_value(subject["planned_tag"], "planned tag")
    unused_destination(api, tag)
    _refresh(root, api, candidate)
    api.write(f"/repos/{policy.REPOSITORY}/git/refs", {
        "ref": "refs/tags/" + tag, "sha": subject["candidate_commit"],
    })
    observed_tag(api, tag, string_value(subject["candidate_commit"], "candidate"))
    release_id = _new_draft(root, api, candidate)
    uploaded: dict[str, int] = {}
    for name, data in sorted(candidate.bundle.files.items()):
        _draft(api, release_id, tag, uploaded)
        _refresh(root, api, candidate)
        uploaded[name] = _upload(api, release_id, name, data)
    observed_release(api, candidate.bundle, release_id=release_id, draft=True)
    _refresh(root, api, candidate)
    api.write(f"/repos/{policy.REPOSITORY}/releases/{release_id}", {
        "draft": False, "make_latest": "true",
    }, method="PATCH")
    _refresh(root, api, candidate)
    observed = observed_release(api, candidate.bundle, release_id=release_id)
    return {"state": "PUBLISHED_UNCERTIFIED", "binding": candidate.binding(),
            "publication": observed, "publication_allowed": False}
