"""Publication authority must not come from a locally fabricated readiness map."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.autonomous_seo_review_trust import candidate_blob_sha256
from scripts.validate_phase6_readiness import REQUIRED, REQUIRED_GATES, validate


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL, timeout=20
    ).strip()


def forged_local_approval(root: Path) -> None:
    """Create internally consistent but unauthenticated synthetic local evidence."""
    for relative in REQUIRED:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}\n", encoding="utf-8")
    for name in ("live.txt", "reproduction.txt"):
        (root / name).write_text("synthetic, not a real observation\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.name", "Publication test fixture")
    _git(root, "config", "user.email", "publication@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "controlled synthetic evidence")
    candidate = _git(root, "rev-parse", "HEAD")
    reviewers = (
        ("final-scrummaster-3-verdict.json", "Senior ScrumMaster 3"),
        ("final-vp-engineering-verdict.json", "VP Engineering"),
    )
    for filename, role in reviewers:
        (root / "evaluation/reviewers" / filename).write_text(json.dumps({
            "reviewer": role, "verdict": "APPROVE_GREAT", "candidate_commit": candidate,
        }), encoding="utf-8")
    (root / "evaluation/comparative/benchmark-cases.json").write_text(
        json.dumps({"execution_state": "PASS"}), encoding="utf-8"
    )
    gates = dict.fromkeys(REQUIRED_GATES, "PASS")
    gates.update(scrummaster3_verdict="APPROVE_GREAT", vp_engineering_verdict="APPROVE_GREAT")
    evidence = {}
    for gate, name in (("live_authorized_smokes", "live.txt"),
                       ("external_reproduction", "reproduction.txt")):
        evidence[gate] = {
            "state": "PASS", "candidate_commit": candidate,
            "evidence_refs": [{"kind": "repository_file", "path": name,
                               "bound_commit": candidate,
                               "sha256": candidate_blob_sha256(root, candidate, name)}],
        }
    readiness = {
        "release_decision": "APPROVED", "evaluated_target_commit": candidate, "gates": gates,
        "verification_state": dict.fromkeys(
            ("code_verified", "live_verified", "externally_reproduced"), "PASS"
        ),
        "verified_ci": {"commit": candidate, "provider": "GitHub Actions", "run_id": 1,
                        "cells": ["not-a-real-platform-cell"]},
        "verification_evidence": evidence,
    }
    (root / "evaluation/comparative/final-release-readiness.json").write_text(
        json.dumps(readiness), encoding="utf-8"
    )


def test_local_approved_labels_and_hashes_cannot_authorize_publication(tmp_path: Path) -> None:
    forged_local_approval(tmp_path)
    assert validate(root=tmp_path) == [], "the forgery must pass legacy consistency first"

    errors = validate(require_approved=True, root=tmp_path)

    assert errors, "local labels, run1/fake cells and hashed synthetic text are not authority"
    assert any("authenticated" in error.lower() for error in errors)
