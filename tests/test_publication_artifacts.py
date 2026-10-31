"""Synthetic byte bundles and gh JSON shapes, never real release authorization."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from contextlib import nullcontext
from copy import deepcopy
from io import BytesIO

import pytest

from scripts import publication_policy as policy
from scripts.publication_artifacts import (
    inspect_result,
    unpack_candidate,
    unpack_result,
    verify_attestation,
)
from scripts.publication_subject import build_subject
from tests.test_publication_provider import CANDIDATE, NOW, TREE


def payloads() -> dict[str, bytes]:
    files = {"world_class_seo_agent_system-1.7.1-py3-none-any.whl": b"controlled wheel bytes",
             "world_class_seo_agent_system-1.7.1.tar.gz": b"controlled sdist bytes",
             "sbom.cdx.json": b'{"bomFormat":"CycloneDX"}',
             "release-manifest.json": b'{"controlled":"manifest"}'}
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")
    return files


def bundle_files() -> dict[str, bytes]:
    files = payloads()
    subject = build_subject(commit=CANDIDATE, tree=TREE, version="1.7.1", ci_run_id=44,
                            ci_attempt=2, prepare_run_id=45, prepare_attempt=1,
                            prepared_at=NOW, payloads=files)
    return {**files, "publication-subject.json": subject}


def zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def verified_shape(name: str, digest: str) -> list[dict[str, object]]:
    """Shape from official gh2.95/Sigstore1.2.1 types; no crypto proof in fixtures."""
    repository_url = "https://github.com/" + policy.REPOSITORY
    signer = repository_url + "/" + policy.PREPARATION_WORKFLOW + "@refs/heads/main"
    invocation = repository_url + "/actions/runs/45/attempts/1"
    return [{"attestation": {"bundle": {"mediaType": "synthetic-test-only"}},
             "verificationResult": {
                 "mediaType": "application/vnd.dev.sigstore.verificationresult+json;version=0.1",
                 "signature": {"certificate": {
                     "issuer": "https://token.actions.githubusercontent.com",
                     "subjectAlternativeName": signer, "buildSignerURI": signer,
                     "buildSignerDigest": CANDIDATE, "runnerEnvironment": "github-hosted",
                     "sourceRepositoryURI": repository_url, "sourceRepositoryDigest": CANDIDATE,
                     "sourceRepositoryRef": "refs/heads/main", "runInvocationURI": invocation}},
                 "verifiedTimestamps": [{"type": "Tlog", "uri": "https://rekor.sigstore.dev",
                                         "timestamp": "2026-10-31T03:00:00Z"}],
                 "statement": {"_type": "https://in-toto.io/Statement/v1",
                               "subject": [{"name": name, "digest": {"sha256": digest}}],
                               "predicateType": policy.PROVENANCE_PREDICATE,
                               "predicate": {"runDetails": {"metadata": {"invocationId": invocation}}}}}}]


def verify(result: object) -> None:
    verify_attestation(result, name="publication-subject.json", digest="d" * 64,
                       repository=policy.REPOSITORY, workflow=policy.PREPARATION_WORKFLOW,
                       source_commit=CANDIDATE, run_id=45, run_attempt=1,
                       predicate_type=policy.PROVENANCE_PREDICATE)


def test_exact_six_member_bundle_binds_source_and_all_approved_bytes() -> None:
    files = bundle_files()
    archive = zip_bytes(files)
    subject, unpacked = unpack_candidate(archive,
                                         expected_archive_sha256=hashlib.sha256(archive).hexdigest(), now=NOW)
    assert subject.get("candidate_commit") == CANDIDATE
    assert unpacked == files


def test_unverified_or_empty_cli_result_cannot_become_attestation_authority() -> None:
    with pytest.raises(ValueError):
        verify({"verified": True})


def test_pinned_execution_result_bytes_are_bound_without_filesystem_extraction() -> None:
    raw = b'{"synthetic_result":"not_authority"}'
    archive = zip_bytes({"execution.json": raw})
    result = unpack_result(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(),
                           member_name="execution.json", member_sha256=hashlib.sha256(raw).hexdigest())
    assert result == raw


def test_completion_inspection_is_bounded_bytes_not_a_completion_approval() -> None:
    raw = b'{"state":"COMPLETION_OBSERVED"}'
    archive = zip_bytes({"publication-completion.json": raw})
    result = inspect_result(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(),
                            member_name="publication-completion.json")
    assert result == raw


def checked(archive: bytes):
    return unpack_candidate(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(), now=NOW)


@pytest.mark.parametrize("bad_name", ["../escape", "dir/file", "dir\\file", "/absolute", "C:drive", "control\nname"])
def test_candidate_archive_rejects_path_or_control_character_members(bad_name) -> None:
    files = bundle_files()
    files[bad_name] = files.pop("sbom.cdx.json")
    with pytest.raises(ValueError):
        checked(zip_bytes(files))


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong_hash", "wrong_size", "no_subject"])
def test_exact_member_set_and_frozen_payload_metadata_are_not_optional(mutation) -> None:
    files = bundle_files()
    if mutation == "missing":
        files.pop("SHA256SUMS")
    elif mutation == "extra":
        files["extra.json"] = b"{}"
    elif mutation == "no_subject":
        files["not-the-subject.json"] = files.pop("publication-subject.json")
    else:
        document = json.loads(files["publication-subject.json"])
        document["files"][0]["sha256" if mutation == "wrong_hash" else "bytes"] = (
            "0" * 64 if mutation == "wrong_hash" else 999)
        files["publication-subject.json"] = json.dumps(document).encode()
    with pytest.raises(ValueError):
        checked(zip_bytes(files))


def test_archive_provider_digest_must_match_actual_archive_bytes() -> None:
    with pytest.raises(ValueError, match="digest"):
        unpack_candidate(zip_bytes(bundle_files()), expected_archive_sha256="0" * 64, now=NOW)


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO])
def test_archive_cannot_supply_symlinks_directories_or_special_files(mode) -> None:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for index, (name, raw) in enumerate(bundle_files().items()):
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = ((mode if index == 0 else stat.S_IFREG) | 0o600) << 16
            archive.writestr(info, raw)
    with pytest.raises(ValueError, match="regular"):
        checked(stream.getvalue())


def test_case_aliased_and_duplicate_members_are_rejected() -> None:
    files = bundle_files()
    rows = list(files.items())
    rows[-1] = (rows[0][0], rows[-1][1])
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, raw in rows:
            with pytest.warns(UserWarning) if name in archive.namelist() else nullcontext():
                archive.writestr(name, raw)
    with pytest.raises(ValueError):
        checked(stream.getvalue())


def test_checksums_cannot_claim_subject_or_self_even_if_subject_hash_is_updated() -> None:
    files = bundle_files()
    files["SHA256SUMS"] += b"0" * 64 + b"  publication-subject.json\n"
    document = json.loads(files["publication-subject.json"])
    for row in document["files"]:
        if row["name"] == "SHA256SUMS":
            row["bytes"] = len(files["SHA256SUMS"])
            row["sha256"] = hashlib.sha256(files["SHA256SUMS"]).hexdigest()
    files["publication-subject.json"] = json.dumps(document).encode()
    with pytest.raises(ValueError, match="checksums"):
        checked(zip_bytes(files))


@pytest.mark.parametrize("bound", ["MAX_ARCHIVE_BYTES", "MAX_EXPANDED_BYTES", "MAX_MEMBER_BYTES"])
def test_archive_resource_limits_are_enforced_before_unbounded_expansion(monkeypatch, bound) -> None:
    archive = zip_bytes(bundle_files())
    monkeypatch.setattr(policy, bound, 1)
    with pytest.raises(ValueError):
        checked(archive)


def test_successful_gh_shape_must_match_exact_subject_and_certificate_invocation() -> None:
    assert verify(verified_shape("publication-subject.json", "d" * 64)) is None


@pytest.mark.parametrize("field,value", [
    ("issuer", "https://untrusted.invalid"), ("runnerEnvironment", "self-hosted"),
    ("sourceRepositoryURI", "https://github.com/other/repo"),
    ("sourceRepositoryDigest", "c" * 40), ("buildSignerDigest", "c" * 40),
    ("buildSignerURI", "https://github.com/wrong/workflow@refs/heads/main"),
    ("runInvocationURI", "https://github.com/other/repo/actions/runs/45/attempts/1"),
])
def test_verified_certificate_must_match_pinned_hosted_source_workflow_and_run(field, value) -> None:
    result = verified_shape("publication-subject.json", "d" * 64)
    result[0]["verificationResult"]["signature"]["certificate"][field] = value
    with pytest.raises(ValueError):
        verify(result)


@pytest.mark.parametrize("mutation", ["empty", "no_certificate", "no_timestamp", "bad_subject", "bad_predicate", "bad_invocation"])
def test_cli_success_or_unverified_predicate_cannot_replace_required_verified_fields(mutation) -> None:
    result = deepcopy(verified_shape("publication-subject.json", "d" * 64))
    record = result[0]["verificationResult"]
    if mutation == "empty":
        result = []
    elif mutation == "no_certificate":
        record["signature"] = {}
    elif mutation == "no_timestamp":
        record["verifiedTimestamps"] = []
    elif mutation == "bad_subject":
        record["statement"]["subject"][0]["digest"]["sha256"] = "e" * 64
    elif mutation == "bad_predicate":
        record["statement"]["predicateType"] = policy.SBOM_PREDICATE
    else:
        record["statement"]["predicate"]["runDetails"]["metadata"]["invocationId"] += "0"
    with pytest.raises(ValueError):
        verify(result)


def test_sbom_uses_verified_certificate_invocation_not_nonexistent_slsa_metadata() -> None:
    result = verified_shape("publication-subject.json", "d" * 64)
    result[0]["verificationResult"]["statement"].update(
        predicateType=policy.SBOM_PREDICATE, predicate={"bomFormat": "CycloneDX"})
    assert verify_attestation(result, name="publication-subject.json", digest="d" * 64,
                              repository=policy.REPOSITORY, workflow=policy.PREPARATION_WORKFLOW,
                              source_commit=CANDIDATE, run_id=45, run_attempt=1,
                              predicate_type=policy.SBOM_PREDICATE) is None


@pytest.mark.parametrize("raw", [b'[]', b'{"duplicate":1,"duplicate":2}', b'{"nonfinite":NaN}'])
def test_result_member_requires_strict_bounded_json_object(raw) -> None:
    archive = zip_bytes({"execution.json": raw})
    with pytest.raises(ValueError):
        inspect_result(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(),
                       member_name="execution.json")


def test_result_wrong_member_digest_or_extra_member_is_rejected() -> None:
    raw = b'{"synthetic_result":"not_authority"}'
    archive = zip_bytes({"execution.json": raw})
    with pytest.raises(ValueError):
        unpack_result(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(),
                      member_name="execution.json", member_sha256="0" * 64)
    with pytest.raises(ValueError):
        archive = zip_bytes({"execution.json": raw, "extra.json": b"{}"})
        inspect_result(archive, expected_archive_sha256=hashlib.sha256(archive).hexdigest(),
                       member_name="execution.json")


def test_malformed_verified_observer_type_is_a_contract_error() -> None:
    result = verified_shape("publication-subject.json", "d" * 64)
    result[0]["verificationResult"]["verifiedTimestamps"][0]["type"] = ["Tlog"]
    with pytest.raises(ValueError):
        verify(result)
