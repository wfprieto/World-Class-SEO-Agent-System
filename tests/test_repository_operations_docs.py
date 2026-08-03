from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs/REPOSITORY-OPERATIONS.md"
CONTROL_ANCHORS = {
    "ops-security-intake",
    "ops-repository-governance",
    "ops-certification-supply-chain",
    "ops-runtime-evidence-integrity",
    "ops-network-provider-boundaries",
    "ops-documentation-knowledge-truth",
    "ops-architecture-quality-debt",
}
CONTROL_IDS = {anchor.removeprefix("ops-") for anchor in CONTROL_ANCHORS}
INTAKE_FIELDS = {"control_id", "owner", "evidence", "verification", "rollback", "safety"}


def test_repository_operations_runbook_has_seven_stable_complete_controls() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    registry = json.loads(
        (ROOT / "governance/repository-operations.json").read_text(encoding="utf-8")
    )

    assert {anchor for anchor in CONTROL_ANCHORS if f'id="{anchor}"' in text} == CONTROL_ANCHORS
    assert {row["id"] for row in registry["critical_paths"]} == CONTROL_IDS
    assert {row["runbook"]["anchor"] for row in registry["critical_paths"]} == CONTROL_ANCHORS
    assert text.count("- **Verify:**") == len(CONTROL_ANCHORS)
    assert text.count("- **Fail:**") == len(CONTROL_ANCHORS)
    assert text.count("- **Recover:**") == len(CONTROL_ANCHORS)
    assert text.count("- **Escalate:**") == len(CONTROL_ANCHORS)
    assert text.count("- **Stop:**") == len(CONTROL_ANCHORS)


def test_operations_docs_preserve_truthful_conduct_and_backup_status() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
    governance = (ROOT / "docs/GOVERNANCE.md").read_text(encoding="utf-8")

    assert "OWNER_ACTION_REQUIRED" in runbook
    assert "OWNER_ACTION_REQUIRED" in support
    assert "OWNER_ACTION_REQUIRED" in governance
    assert "has not yet been designated" in support
    assert "must not be represented as a completed conduct-reporting channel" in support


def test_conduct_owner_checklist_preserves_owner_boundary_and_sensitive_data_rules() -> None:
    runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
    required = (
        "Owner provisioning checklist",
        "Select and provision one repository-controlled route",
        "Explicitly authorize publication",
        "Send a benign access test",
        "provider-controlled, immutable verification",
        "repository issue comment, repository commit, self-authored assertion",
        "acknowledgement target, monitoring role, confidentiality limits, and conflict handling",
        "restore `BLOCKED_OWNER_ACTION`",
    )
    assert all(text in runbook for text in required)
    prohibited = (
        "mailbox content",
        "credentials",
        "reporter identity",
        "report content",
        "private access URL",
    )
    assert all(text in runbook for text in prohibited)


def test_yaml_issue_forms_require_operational_traceability_and_privacy() -> None:
    for name in ("bug_report.yml", "feature_request.yml", "support_request.yml"):
        path = ROOT / ".github/ISSUE_TEMPLATE" / name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        body = document["body"]
        by_id = {row.get("id"): row for row in body if isinstance(row, dict) and row.get("id")}

        assert set(by_id) >= INTAKE_FIELDS, name
        for field in INTAKE_FIELDS - {"safety"}:
            assert by_id[field]["validations"]["required"] is True, f"{name}:{field}"
        assert all(
            option["required"] is True
            for option in by_id["safety"]["attributes"]["options"]
        ), f"{name}:safety"
        safety_text = " ".join(
            option["label"] for option in by_id["safety"]["attributes"]["options"]
        )
        assert "vulnerability details" in safety_text
        assert "private conduct reports" in safety_text


def test_markdown_intake_and_pull_request_templates_have_required_controls() -> None:
    paths = (
        ROOT / ".github/PULL_REQUEST_TEMPLATE.md",
        ROOT / ".github/ISSUE_TEMPLATE/agent_improvement.md",
        ROOT / ".github/ISSUE_TEMPLATE/skill_request.md",
    )
    required = (
        "Control ID",
        "owner",
        "Evidence",
        "Verification",
        "Rollback",
        "private conduct report",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert all(token.lower() in lowered for token in required), path.name
