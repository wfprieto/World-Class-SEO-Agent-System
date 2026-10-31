"""Read bounded regular evidence blobs at exact Git objects without executing E."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from scripts.publication_policy import MAX_EVIDENCE_BYTES, MAX_RECORD_BYTES, MAX_RECORDS
from scripts.publication_transport import run_bounded

ENTRY = "publication-evidence/evidence.json"
RECORD = re.compile(r"publication-evidence/records/[0-9a-f]{64}\.json\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def git(root: Path, *args: str) -> bytes:
    executable = shutil.which("git")
    if executable is None or Path(executable).resolve().is_relative_to(root.resolve()):
        raise ValueError("Trusted Git executable is unavailable")
    return run_bounded([executable, *args], cwd=root, limit=MAX_EVIDENCE_BYTES, timeout=20)


def _validate_changes(root: Path, source: str, evidence: str) -> None:
    raw = git(root, "diff-tree", "--raw", "-r", "-z", "--no-renames", "--no-abbrev",
              source, evidence).split(b"\0")
    if raw[-1] != b"" or len(raw) % 2 != 1:
        raise ValueError("Invalid raw Git evidence inventory")
    for header, name in zip(raw[0:-1:2], raw[1:-1:2], strict=True):
        fields = header.decode("ascii").split()
        path = name.decode("ascii")
        if (len(fields) != 5 or fields[0] not in {":000000", ":100644"}
                or fields[1] != "100644" or fields[4] not in {"A", "M"}
                or (path != ENTRY and RECORD.fullmatch(path) is None)):
            raise ValueError("Evidence PR changes source, unsafe modes or unknown data paths")


def _read_members(root: Path, evidence: str) -> dict[str, bytes]:
    inventory = git(root, "ls-tree", "-r", "-z", evidence, "--", "publication-evidence")
    members = inventory.split(b"\0")[:-1]
    if not 1 <= len(members) <= MAX_RECORDS:
        raise ValueError("Evidence file count exceeds the contract")
    records: dict[str, bytes] = {}
    total = 0
    for entry in members:
        metadata, raw_name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        name = raw_name.decode("ascii")
        if mode != "100644" or kind != "blob" or (name != ENTRY and not RECORD.fullmatch(name)):
            raise ValueError("Evidence contains unsafe Git modes or paths")
        size = int(git(root, "cat-file", "-s", blob))
        total += size
        if not 1 <= size <= MAX_RECORD_BYTES or total > MAX_EVIDENCE_BYTES:
            raise ValueError("Evidence bytes exceed the contract")
        content = git(root, "cat-file", "blob", blob)
        if len(content) != size or (name != ENTRY and Path(name).stem
                                   != hashlib.sha256(content).hexdigest()):
            raise ValueError("Evidence content-addressed bytes do not match")
        records[name] = content
    return records


def read_evidence(root: Path, source: str, evidence: str) -> tuple[bytes, dict[str, bytes], str]:
    if SHA.fullmatch(source) is None or SHA.fullmatch(evidence) is None or source == evidence:
        raise ValueError("Evidence requires distinct full source and evidence commits")
    git(root, "merge-base", "--is-ancestor", source, evidence)
    _validate_changes(root, source, evidence)
    records = _read_members(root, evidence)
    if ENTRY not in records:
        raise ValueError("Evidence entry is missing")
    inventory = [{"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                 for path, data in sorted(records.items())]
    digest = hashlib.sha256(json.dumps(inventory, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    return records.pop(ENTRY), records, digest
