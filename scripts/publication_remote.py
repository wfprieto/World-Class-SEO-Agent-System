"""Exact public-byte readback and a fixed GitHub asset-upload endpoint."""

from __future__ import annotations

import hashlib
import json
import re

from scripts import publication_policy as policy
from scripts.publication_bundle import CandidateBundle
from scripts.publication_provider import repository_identity
from scripts.publication_subject import (
    JsonObject,
    instant,
    integer_value,
    object_value,
    string_value,
)
from scripts.publication_transport import GitHubCLI


def _tag(tag: str) -> str:
    if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is None:
        raise ValueError("Publication tag must be an exact semantic version")
    return tag


def items(api: GitHubCLI, path: str) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for page in range(1, policy.MAX_API_PAGES + 1):
        data = api.json(f"{path}?per_page={policy.PAGE_SIZE}&page={page}")
        if not isinstance(data, list) or len(data) > policy.PAGE_SIZE:
            raise ValueError("Provider list response is malformed")
        rows.extend(object_value(row, "provider list item") for row in data)
        if len(data) < policy.PAGE_SIZE:
            return rows
    raise ValueError("Provider list exceeded its complete-pagination boundary")


def unused_destination(api: GitHubCLI, tag: str) -> None:
    tag = _tag(tag)
    prefix = f"/repos/{policy.REPOSITORY}"
    references = api.json(prefix + "/git/matching-refs/tags/" + tag)
    if not isinstance(references, list):
        raise ValueError("Provider tag inventory is unavailable")
    if any(object_value(row, "tag reference").get("ref") == "refs/tags/" + tag for row in references):
        raise ValueError("Tag already exists; partial publication cannot be automatically resumed")
    if any(row.get("tag_name") == tag for row in items(api, prefix + "/releases")):
        raise ValueError("Release already exists; partial publication cannot be automatically resumed")


def observed_tag(api: GitHubCLI, tag: str, commit: str) -> JsonObject:
    reference = object_value(api.json(f"/repos/{policy.REPOSITORY}/git/ref/tags/{_tag(tag)}"), "tag")
    target = object_value(reference.get("object"), "tag target")
    if (reference.get("ref") != "refs/tags/" + tag
            or target.get("type") != "commit" or target.get("sha") != commit):
        raise ValueError("Actual publication tag does not name the exact candidate commit")
    return reference


def _observed_assets(api: GitHubCLI, bundle: CandidateBundle, release_id: int) -> list[JsonObject]:
    assets = items(api, f"/repos/{policy.REPOSITORY}/releases/{release_id}/assets")
    if len(assets) != len(bundle.files):
        raise ValueError("Release must contain exactly the six approved prepared files")
    observed: list[JsonObject] = []
    names: set[str] = set()
    identities: set[int] = set()
    for asset in assets:
        name = string_value(asset.get("name"), "asset name")
        identity = integer_value(asset.get("id"), "asset ID")
        if name not in bundle.files or name in names or identity in identities:
            raise ValueError("Release has an unexpected or duplicate asset identity")
        names.add(name)
        identities.add(identity)
        expected = bundle.files[name]
        digest = hashlib.sha256(expected).hexdigest()
        if (integer_value(asset.get("size"), "asset size") != len(expected)
                or asset.get("state") != "uploaded" or asset.get("digest") != "sha256:" + digest):
            raise ValueError("Actual asset metadata disagrees with the approved prepared bytes")
        actual = api.command(["api", "--hostname", "github.com",
                              f"repos/{policy.REPOSITORY}/releases/assets/{identity}",
                              "--header", "Accept: application/octet-stream"], limit=policy.MAX_MEMBER_BYTES)
        if actual != expected:
            raise ValueError("Actual downloaded release bytes differ from the prepared artifact")
        observed.append({"id": identity, "name": name, "bytes": len(actual), "sha256": digest})
    return sorted(observed, key=lambda row: str(row["name"]))


def observed_release(api: GitHubCLI, bundle: CandidateBundle, *,
                     release_id: int | None = None, draft: bool = False) -> JsonObject:
    repository = object_value(api.json(f"/repos/{policy.REPOSITORY}"), "repository")
    repository_identity(repository, policy.REPOSITORY, policy.REPOSITORY_ID, policy.OWNER_ID)
    if repository.get("private") is not False:
        raise ValueError("A private repository cannot satisfy public distribution")
    tag = string_value(bundle.subject["planned_tag"], "planned tag")
    observed_tag(api, tag, string_value(bundle.subject["candidate_commit"], "candidate"))
    suffix = str(integer_value(release_id, "release ID")) if release_id is not None else "tags/" + tag
    release = object_value(api.json(f"/repos/{policy.REPOSITORY}/releases/{suffix}"), "release")
    identity = integer_value(release.get("id"), "release ID")
    if (release.get("tag_name") != tag or release.get("draft") is not draft
            or release.get("prerelease") is not False
            or (release_id is not None and identity != release_id)):
        raise ValueError("Actual release identity or publication state does not match")
    if not draft:
        instant(release.get("published_at"), "actual publication time")
    assets = _observed_assets(api, bundle, identity)
    return {"release_id": identity, "tag": tag, "draft": draft, "assets": assets,
            "published_at": release.get("published_at"),
            "platform_immutable": release.get("immutable") is True}


def upload_asset(api: GitHubCLI, release_id: int, name: str, data: bytes) -> JsonObject:
    integer_value(release_id, "release ID")
    if (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}", name) is None
            or not data or len(data) > policy.MAX_MEMBER_BYTES):
        raise ValueError("Upload requires one flat bounded approved asset")
    endpoint = (f"https://uploads.github.com/repos/{policy.REPOSITORY}/releases/{release_id}"
                f"/assets?name={name}")
    result: object = json.loads(api.command([
        "api", "--hostname", "github.com", endpoint, "--method", "POST", "--input", "-",
        "--header", "Content-Type: application/octet-stream", "--header", f"Content-Length: {len(data)}",
    ], body=data))
    return object_value(result, "uploaded asset")
