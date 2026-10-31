"""The public entry point fails closed without genuine enrolled execution origins."""

import json

import pytest

from scripts import publication_cli
from scripts.publication_policy import EXECUTION_GATES, REQUIRED_GATES


def test_status_cannot_promote_deny_all_origin_policy(capsys: pytest.CaptureFixture[str]) -> None:
    assert publication_cli.main(["status"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["state"] == "BLOCKED"
    assert data["publication_allowed"] is False
    assert set(data["missing_execution_authorities"]) == EXECUTION_GATES
    assert set(data["required_final_gates"]) == REQUIRED_GATES


def test_publisher_outside_actual_workflow_cannot_write(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert publication_cli.main([
        "publish", "--prepare-run-id", "2", "--artifact-id", "3", "--evidence-pr", "4",
        "--owner-comment-id", "5",
    ]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "BLOCKED"
    assert "workflow" in result["reason"].lower()
