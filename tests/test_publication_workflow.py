"""Public workflow boundaries for publication of already-reviewed bytes."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_publication_separates_authorization_writes_and_final_completion() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())

    assert set(workflow["jobs"]) == {"authorize", "publish", "complete"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["authorize"]["permissions"]["contents"] == "read"
    assert workflow["jobs"]["publish"]["permissions"]["contents"] == "write"
    assert workflow["jobs"]["complete"]["permissions"]["contents"] == "read"


def test_write_privileged_publisher_does_not_build_or_install_dependencies() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    publishers = [job for job in workflow["jobs"].values()
                  if job.get("permissions", {}).get("contents") == "write"]

    assert len(publishers) == 1
    commands = "\n".join(str(step.get("run", "")) for step in publishers[0]["steps"])
    assert "pip install" not in commands, "publication credentials must not run installers"
    assert "python -m build" not in commands, "publish only previously reviewed artifact bytes"
