"""Exact public-byte and no-replacement policy uses synthetic provider responses only."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts import publication_policy as policy
from scripts.publication_bundle import CandidateBundle
from scripts.publication_remote import observed_release, unused_destination
from tests.test_publication_artifacts import bundle_files
from tests.test_publication_provider import CANDIDATE


class RemoteAPI:
    def __init__(self) -> None:
        self.files = bundle_files()
        self.private = False
        self.commit = CANDIDATE
        self.tag_exists = False
        self.listed_releases: list[object] = []
        self.release = {"id": 81, "tag_name": "v1.7.1", "draft": False,
                        "prerelease": False, "published_at": "2026-10-31T03:00:00Z"}
        self.assets = [{"id": index + 1, "name": name, "size": len(raw), "state": "uploaded",
                        "digest": "sha256:" + hashlib.sha256(raw).hexdigest()}
                       for index, (name, raw) in enumerate(self.files.items())]
        self.raw = {index + 1: raw for index, raw in enumerate(self.files.values())}

    def json(self, path: str) -> object:
        prefix = f"/repos/{policy.REPOSITORY}"
        if path == prefix:
            return {"id": policy.REPOSITORY_ID, "full_name": policy.REPOSITORY,
                    "owner": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN},
                    "private": self.private}
        if "/git/matching-refs/" in path:
            return [{"ref": "refs/tags/v1.7.1"}] if self.tag_exists else []
        if path == prefix + "/git/ref/tags/v1.7.1":
            return {"ref": "refs/tags/v1.7.1", "object": {"type": "commit", "sha": self.commit}}
        if path == prefix + "/releases?per_page=100&page=1":
            return self.listed_releases
        if path == prefix + "/releases/81/assets?per_page=100&page=1":
            return self.assets
        if path in {prefix + "/releases/81", prefix + "/releases/tags/v1.7.1"}:
            return self.release
        raise AssertionError(f"unexpected synthetic API path: {path}")

    def command(self, args: list[str], *, limit: int) -> bytes:
        identity = int(args[3].rsplit("/", 1)[1])
        assert args[:3] == ["api", "--hostname", "github.com"]
        assert args[-2:] == ["--header", "Accept: application/octet-stream"]
        assert len(self.raw[identity]) <= limit
        return self.raw[identity]


def _bundle(api: RemoteAPI) -> CandidateBundle:
    return CandidateBundle(json.loads(api.files["publication-subject.json"]), api.files, 77, "d" * 64)


def test_remote_readback_uses_actual_bytes_for_all_six_assets() -> None:
    api = RemoteAPI()
    result = observed_release(api, _bundle(api))
    assert result["release_id"] == 81
    assert len(result["assets"]) == 6


@pytest.mark.parametrize("change", ["private", "tag", "draft", "bytes", "missing", "extra"])
def test_remote_readback_rejects_nonpublic_or_substituted_publication(change: str) -> None:
    api = RemoteAPI()
    if change == "private":
        api.private = True
    elif change == "tag":
        api.commit = "e" * 40
    elif change == "draft":
        api.release["draft"] = True
    elif change == "bytes":
        api.raw[1] = b"substitution"
    elif change == "missing":
        api.assets.pop()
    else:
        api.assets.append({**api.assets[0], "id": 99, "name": "unexpected.json"})
    with pytest.raises(ValueError):
        observed_release(api, _bundle(api))


def test_unused_destination_accepts_only_absent_tag_and_release() -> None:
    unused_destination(RemoteAPI(), "v1.7.1")


@pytest.mark.parametrize("existing", ["tag", "release"])
def test_existing_partial_publication_cannot_be_automatically_resumed(existing: str) -> None:
    api = RemoteAPI()
    api.tag_exists = existing == "tag"
    api.listed_releases = [{"tag_name": "v1.7.1"}] if existing == "release" else []
    with pytest.raises(ValueError):
        unused_destination(api, "v1.7.1")
