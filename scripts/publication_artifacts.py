"""Bounded approved-byte archives and post-cryptographic attestation policy."""

from __future__ import annotations

import hashlib
import re
import stat
import zipfile
import zlib
from datetime import datetime
from io import BytesIO

from scripts import publication_policy as policy
from scripts.publication_provider import integer_value, text_value, timestamp
from scripts.publication_subject import (
    JsonObject,
    json_object,
    object_value,
    parse_subject,
    sha_value,
    subject_files,
)
from scripts.publication_zip import directory_start, read_member


def _flat_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    mode = (info.external_attr >> 16) & 0o170000
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", name)
            or info.orig_filename != name or info.is_dir() or info.external_attr & 0x10
            or mode not in {0, stat.S_IFREG} or info.flag_bits & 1
            or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}):
        raise ValueError("archive member must be a safe flat regular unencrypted file")


def _unpack(raw: bytes, digest: str, count: int, member_limit: int) -> dict[str, bytes]:
    sha_value(digest, 64, "archive digest")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= policy.MAX_ARCHIVE_BYTES:
        raise ValueError("archive compressed size exceeds its bound")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("archive does not match its authenticated provider digest")
    central = directory_start(raw, count)
    files: dict[str, bytes] = {}
    folded: set[str] = set()
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            infos = sorted(archive.infolist(), key=lambda info: info.header_offset)
            if len(infos) != count or infos[0].header_offset != 0:
                raise ValueError("archive member count mismatch")
            if sum(info.file_size for info in infos) > policy.MAX_EXPANDED_BYTES:
                raise ValueError("archive expanded size exceeds its bound")
            expanded = 0
            for index, info in enumerate(infos):
                _flat_member(info)
                if info.filename.casefold() in folded or not 0 < info.file_size <= member_limit:
                    raise ValueError("archive contains duplicate/aliased or oversized members")
                folded.add(info.filename.casefold())
                boundary = infos[index + 1].header_offset if index + 1 < len(infos) else central
                data = read_member(raw, info, boundary=boundary,
                                   limit=min(member_limit, policy.MAX_EXPANDED_BYTES - expanded))
                expanded += len(data)
                files[info.filename] = data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, UnicodeError, zlib.error):
        raise ValueError("archive integrity or compression is invalid") from None
    return files


def _checksums(files: dict[str, bytes]) -> None:
    expected = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()
                if name not in {"publication-subject.json", "SHA256SUMS"}}
    actual: dict[str, str] = {}
    try:
        for line in files["SHA256SUMS"].decode("ascii").splitlines():
            digest, separator, name = line.partition("  ")
            if not separator or name in actual or name not in expected:
                raise ValueError("checksums contain extra, duplicate or self-referential rows")
            actual[name] = digest
    except UnicodeError:
        raise ValueError("checksums must be bounded ASCII rows") from None
    if actual != expected:
        raise ValueError("checksums must cover exactly the four other payload bytes")


def unpack_candidate(
    archive: bytes, *, expected_archive_sha256: str, now: datetime,
) -> tuple[JsonObject, dict[str, bytes]]:
    files = _unpack(archive, expected_archive_sha256, 6, policy.MAX_MEMBER_BYTES)
    if "publication-subject.json" not in files:
        raise ValueError("candidate archive requires its detached subject")
    subject = parse_subject(files["publication-subject.json"], now=now)
    expected = subject_files(subject)
    if set(files) != set(expected) | {"publication-subject.json"}:
        raise ValueError("candidate archive contains missing or unexpected payloads")
    for name, record in expected.items():
        if (len(files[name]) != record["bytes"]
                or hashlib.sha256(files[name]).hexdigest() != record["sha256"]):
            raise ValueError("candidate payload bytes do not match the frozen subject")
    _checksums(files)
    return subject, files


def unpack_result(
    archive: bytes, *, expected_archive_sha256: str, member_name: str,
    member_sha256: str,
) -> bytes:
    """Verify a pinned execution-result archive; hashes alone grant no authority."""
    sha_value(member_sha256, 64, "execution member digest")
    raw = inspect_result(archive, expected_archive_sha256=expected_archive_sha256,
                         member_name=member_name)
    if hashlib.sha256(raw).hexdigest() != member_sha256:
        raise ValueError("execution result bytes disagree with the authenticated pointer")
    return raw


def inspect_result(
    archive: bytes, *, expected_archive_sha256: str, member_name: str,
) -> bytes:
    """Inspect bounded completion bytes; caller must verify cryptographic provenance."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", member_name) is None:
        raise ValueError("result member must be a safe flat JSON filename")
    files = _unpack(archive, expected_archive_sha256, 1, policy.MAX_RECORD_BYTES)
    if set(files) != {member_name}:
        raise ValueError("result archive must contain only its exact named JSON member")
    raw = files[member_name]
    json_object(raw, "execution/completion result")
    return raw


def _certificate(
    value: object, *, repository: str, workflow: str, source_commit: str, invocation: str,
) -> None:
    cert = object_value(value, "verified certificate")
    reference = text_value(cert.get("sourceRepositoryRef"), "verified source ref")
    if re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9_./-]+", reference) is None:
        raise ValueError("verified certificate source ref is invalid")
    signer = f"https://github.com/{repository}/{workflow}@{reference}"
    required = {"issuer": "https://token.actions.githubusercontent.com",
                "subjectAlternativeName": signer, "buildSignerURI": signer,
                "buildSignerDigest": source_commit, "runnerEnvironment": "github-hosted",
                "sourceRepositoryURI": f"https://github.com/{repository}",
                "sourceRepositoryDigest": source_commit, "runInvocationURI": invocation}
    if any(cert.get(key) != expected for key, expected in required.items()):
        raise ValueError("verified certificate signer/source/hosted invocation mismatch")


def _observer_times(value: object) -> None:
    if not isinstance(value, list) or not 0 < len(value) <= 100:
        raise ValueError("verified observer timestamps are missing")
    for item in value:
        row = object_value(item, "verified timestamp")
        if (not isinstance(row.get("type"), str) or row.get("type") not in {"Tlog", "TimestampAuthority"}
                or not text_value(row.get("uri"), "observer URI")):
            raise ValueError("attestation requires a verified external observer timestamp")
        timestamp(row.get("timestamp"), "verified timestamp")


def _verified_entry(
    entry: object, *, name: str, digest: str, repository: str, workflow: str,
    source_commit: str, invocation: str, predicate_type: str,
) -> None:
    item = object_value(entry, "gh verified result")
    if not object_value(item.get("attestation"), "verified attestation bundle"):
        raise ValueError("verified attestation bundle is missing")
    result = object_value(item.get("verificationResult"), "gh verificationResult")
    if result.get("mediaType") != "application/vnd.dev.sigstore.verificationresult+json;version=0.1":
        raise ValueError("unsupported gh verification result")
    signature = object_value(result.get("signature"), "verified signature")
    _certificate(signature.get("certificate"), repository=repository, workflow=workflow,
                 source_commit=source_commit, invocation=invocation)
    _observer_times(result.get("verifiedTimestamps"))
    statement = object_value(result.get("statement"), "verified statement")
    if statement.get("_type") != "https://in-toto.io/Statement/v1" or statement.get("predicateType") != predicate_type:
        raise ValueError("verified attestation predicate type mismatch")
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or not 0 < len(subjects) <= 100:
        raise ValueError("verified attestation subjects are missing")
    matching = [object_value(row, "verified subject") for row in subjects
                if object_value(row, "verified subject").get("name") == name]
    if len(matching) != 1 or matching[0].get("digest") != {"sha256": digest}:
        raise ValueError("verified attestation subject identity mismatch")
    predicate = object_value(statement.get("predicate"), "verified predicate")
    if predicate_type == policy.PROVENANCE_PREDICATE:
        details = object_value(predicate.get("runDetails"), "provenance run details")
        metadata = object_value(details.get("metadata"), "provenance metadata")
        if metadata.get("invocationId") != invocation:
            raise ValueError("verified provenance invocation mismatch")


def verify_attestation(
    result: object, *, name: str, digest: str, repository: str, workflow: str,
    source_commit: str, run_id: int, run_attempt: int, predicate_type: str,
) -> None:
    """Only call after the real gh verifier succeeds with required cert flags."""
    sha_value(digest, 64, "attested digest")
    sha_value(source_commit, 40, "attested source")
    integer_value(run_id, "attested run")
    integer_value(run_attempt, "attested attempt")
    if not isinstance(result, list) or not 0 < len(result) <= 100:
        raise ValueError("gh must return nonempty verified attestation results")
    invocation = f"https://github.com/{repository}/actions/runs/{run_id}/attempts/{run_attempt}"
    for item in result:
        try:
            _verified_entry(item, name=name, digest=digest, repository=repository,
                            workflow=workflow, source_commit=source_commit,
                            invocation=invocation, predicate_type=predicate_type)
        except ValueError:
            continue
        return
    raise ValueError("no verified attestation matches the exact frozen subject and execution")
