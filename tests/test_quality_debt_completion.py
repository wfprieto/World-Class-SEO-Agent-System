"""Fresh measurements must not consume persistent lint/import caches."""

from __future__ import annotations

import copy
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest
import yaml

from contracts.google import GoogleAPIError
from integrations.google.client import GoogleJsonClient
from scripts import validate_quality_ratchets as ratchets
from scripts.workflow_quality_contract import COVERAGE_TARGETS
from scripts.workflow_quality_contract import workflow_errors as _workflow_errors
from seoctl.composition import build_pagespeed_adapter

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("required_flag", ["-B", "--no-cache"])
def test_ratchet_ruff_measurement_disables_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required_flag: str
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
        calls.append((command, kwargs))
        return CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(ratchets.subprocess, "run", run)
    assert ratchets._ruff_counts(tmp_path) == Counter()
    assert len(calls) == 1
    command, options = calls[0]
    assert command[0] == sys.executable
    assert required_flag in command, "canonical lint measurement must execute fresh source analysis"
    assert options["cwd"] == tmp_path
    assert options["timeout"] == 120
    assert set(ratchets.PACKAGES).issubset(command)
    assert command[command.index("--select") + 1] == ",".join(ratchets.RUFF_RULES)


PROPAGATED_FLOORS = {
    "adapters/evidence_identity.py": 67,
    "adapters/evidence_migrations.py": 67,
    "adapters/llm_transport.py": 64,
    "contracts/google.py": 68,
    "contracts/llm_transport.py": 64,
    "integrations/google/oauth.py": 68,
    "integrations/google/transport.py": 68,
    "integrations/google/gsc_results.py": 62,
    "seoctl/composition.py": 83
}


@pytest.mark.parametrize("relative,minimum", PROPAGATED_FLOORS.items())
def test_moved_critical_logic_keeps_original_coverage_protection(
    relative: str, minimum: int,
) -> None:
    contract = json.loads((ROOT / "governance/code-quality-ratchet.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert ratchets.MINIMUM_CRITICAL_COVERAGE.get(relative, -1) >= minimum, (
        "extraction must not move executable critical logic outside immutable coverage floors"
    )
    assert contract["coverage"]["critical_file_floors"].get(relative, -1) >= minimum
    assert project["tool"]["wcseo"]["risk_coverage"].get(relative, -1) >= minimum
    for lowered in (None, minimum - 1):
        altered = copy.deepcopy(contract)
        if lowered is None:
            altered["coverage"]["critical_file_floors"].pop(relative, None)
        else:
            altered["coverage"]["critical_file_floors"][relative] = lowered
        assert any(relative in error for error in ratchets._canonical_policy_errors(altered))


def test_actual_ci_coverage_includes_neutral_executable_contracts() -> None:
    assert "contracts" in COVERAGE_TARGETS
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    job = yaml.safe_load(workflow)["jobs"]["quality_security_release"]
    command = next(step["run"] for step in job["steps"] if step.get("name") == "Run coverage gate")
    assert "--cov=contracts" in command
    assert not _workflow_errors(workflow, 78.0)
    changed = workflow.replace("--cov=contracts ", "", 1)
    assert changed != workflow
    assert _workflow_errors(changed, 78.0), "omitting moved contract execution must fail closed"


def test_whole_tree_lint_is_mandatory_and_exact() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    job = yaml.safe_load(workflow)["jobs"]["quality_security_release"]
    step = next(step for step in job["steps"] if step.get("name") == "Lint canonical P3 profile")
    command = step["run"]
    assert command == "ruff check . --no-cache"
    assert "continue-on-error" not in step
    assert not _workflow_errors(workflow, 78.0)
    for replacement in (
        "ruff check runtime adapters integrations seoctl scripts security --no-cache",
        "ruff check . --no-cache --exclude security",
        "ruff check . --no-cache || true",
        "python -c 'pass'",
    ):
        mutated = workflow.replace(command, replacement, 1)
        assert mutated != workflow
        assert _workflow_errors(mutated, 78.0)
    masked = workflow.replace(
        "        run: ruff check . --no-cache",
        "        run: ruff check . --no-cache\n        continue-on-error: true",
        1,
    )
    assert masked != workflow
    assert _workflow_errors(masked, 78.0)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://www.googleapis.com/forbidden",
        "https://attacker.invalid/forbidden",
        "http://pagespeedonline.googleapis.com/forbidden",
    ],
)
def test_composed_pagespeed_keeps_transport_policy_and_limits(
    endpoint: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    adapter = build_pagespeed_adapter(
        "synthetic-key", crux_api_key="synthetic-crux", timeout=11.5,
        max_retries=1, max_response_bytes=4096, sleep=slept.append,
    )
    client = adapter._client
    assert isinstance(client, GoogleJsonClient)
    assert client.allowed_hosts == {"pagespeedonline.googleapis.com", "chromeuxreport.googleapis.com"}
    assert client.timeout == 11.5
    assert client.max_retries == 1
    assert client.max_response_bytes == 4096
    assert client.sleep == slept.append

    def forbidden_open(*args: object, **kwargs: object) -> None:
        pytest.fail("unapproved PageSpeed endpoint must be denied before any dial")

    monkeypatch.setattr(client.opener, "open", forbidden_open)
    with pytest.raises(GoogleAPIError, match="endpoint is not an approved HTTPS Google API host") as caught:
        client.request(endpoint, service="pagespeed", method="GET")
    assert caught.value.state == "BLOCKED"
    assert slept == []
