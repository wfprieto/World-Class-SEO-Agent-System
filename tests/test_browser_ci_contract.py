"""Real-browser certification cannot silently become an optional skipped check."""

from pathlib import Path

from scripts.workflow_quality_contract import workflow_errors


def test_browser_certification_is_bound_into_required_matrix():
    workflow = Path(".github/workflows/validate.yml").read_text(encoding="utf-8")
    command = "pytest -q --browser-security --junitxml=pytest-results.xml"
    install = "python -m playwright install --with-deps chromium"
    assert command in workflow
    assert install in workflow
    assert workflow_errors(
        workflow.replace(command, command.replace("--browser-security ", "")), 78
    )
    assert workflow_errors(workflow.replace(install, "python -c 'pass'"), 78)
