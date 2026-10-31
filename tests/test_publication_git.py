"""Evidence is immutable data, never a checked-out or executable source branch."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

import pytest

from scripts.publication_git import read_evidence


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True,
                                   stderr=subprocess.DEVNULL, timeout=20).strip()


def _evidence_repository(root: Path, mutation: str = "") -> tuple[str, str, bytes, str, bytes]:
    _git(root, "init")
    _git(root, "config", "user.name", "Evidence fixture")
    _git(root, "config", "user.email", "evidence@example.invalid")
    _git(root, "config", "core.autocrlf", "false")
    (root / "README.md").write_text("source\n", encoding="utf-8", newline="\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "source")
    source = _git(root, "rev-parse", "HEAD")
    raw = b'{"observed":true}\n'
    name = "publication-evidence/records/" + hashlib.sha256(raw).hexdigest() + ".json"
    (root / name).parent.mkdir(parents=True)
    (root / name).write_bytes(raw)
    entry = b'{"candidate":"fixture only"}\n'
    entry_path = root / "publication-evidence/evidence.json"
    entry_path.write_bytes(entry)
    if mutation == "code":
        (root / "README.md").write_text("unreviewed source mutation\n", encoding="utf-8")
    elif mutation == "digest":
        (root / name).write_bytes(b'{"changed":true}\n')
    elif mutation == "namespace":
        (root / "publication-evidence/extra.json").write_bytes(b"{}")
    _git(root, "add", ".")
    if mutation == "executable":
        mode = stat.S_IMODE(entry_path.stat().st_mode)
        entry_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        _git(root, "update-index", "--chmod=+x", "publication-evidence/evidence.json")
    elif mutation == "deletion":
        _git(root, "rm", "README.md")
    _git(root, "commit", "-m", "immutable evidence fixture")
    evidence = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "--detach", source)
    return source, evidence, entry, name, raw


def test_read_evidence_uses_exact_git_blobs_without_checking_out_e(tmp_path: Path) -> None:
    source, evidence, entry, name, raw = _evidence_repository(tmp_path)

    found, records, digest = read_evidence(tmp_path, source, evidence)

    inventory = [{"path": path, "sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
                 for path, value in sorted({"publication-evidence/evidence.json": entry,
                                            name: raw}.items())]
    expected = hashlib.sha256(json.dumps(inventory, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    assert (found, records, digest) == (entry, {name: raw}, expected)
    assert _git(tmp_path, "rev-parse", "HEAD") == source
    assert not (tmp_path / "publication-evidence").exists()


@pytest.mark.parametrize("mutation", ["code", "digest", "namespace", "executable", "deletion"])
def test_read_evidence_rejects_unsafe_or_changed_subjects(tmp_path: Path, mutation: str) -> None:
    source, evidence, *_ = _evidence_repository(tmp_path, mutation)

    assert _git(tmp_path, "rev-parse", "HEAD") == source
    if mutation == "executable":
        entry = _git(tmp_path, "ls-tree", evidence, "--", "publication-evidence/evidence.json")
        assert entry.split()[:2] == ["100755", "blob"]

    with pytest.raises(ValueError, match="unsafe modes" if mutation == "executable" else None):
        read_evidence(tmp_path, source, evidence)

    assert _git(tmp_path, "rev-parse", "HEAD") == source
