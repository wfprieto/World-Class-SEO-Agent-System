"""Every critical command and token boundary is a fail-closed sealed contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.publication_workflow_contract import publication_workflow_errors

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"prepare": "prepare-publication.yml", "release": "release.yml"}


def _workflow(kind: str) -> str:
    return (ROOT / ".github/workflows" / KINDS[kind]).read_text(encoding="utf-8")


def _document(kind: str) -> dict:
    value = yaml.safe_load(_workflow(kind))
    value["on"] = value.pop(True)
    return value


@pytest.mark.parametrize("kind", KINDS)
def test_current_workflow_is_exact_allowed_profile(kind: str) -> None:
    assert publication_workflow_errors(_workflow(kind), kind=kind) == []
    assert publication_workflow_errors(yaml.safe_dump(_document(kind)), kind=kind) == []


def _commands() -> list[tuple[str, str, int]]:
    result = []
    for kind in KINDS:
        document = _document(kind)
        for name, job in document["jobs"].items():
            for index, step in enumerate(job["steps"]):
                command = str(step.get("run", ""))
                if "scripts.publication_cli" in command or "pip install" in command:
                    result.append((kind, name, index))
    return result


@pytest.mark.parametrize("kind,job,index", _commands())
def test_each_critical_command_cannot_be_masked_or_replaced(kind: str, job: str, index: int) -> None:
    document = _document(kind)
    document["jobs"][job]["steps"][index]["run"] = "true"
    assert publication_workflow_errors(yaml.safe_dump(document), kind=kind)


@pytest.mark.parametrize("change", ["write_build", "oidc_build", "publisher_needs", "complete_needs",
                                   "tag_trigger", "unprotected_ref", "clobber", "skip_verify"])
def test_protection_and_order_mutations_are_denied(change: str) -> None:
    kind = "prepare" if change in {"write_build", "oidc_build", "clobber", "skip_verify"} else "release"
    document = _document(kind)
    jobs = document["jobs"]
    if change == "write_build":
        jobs["build"]["permissions"]["contents"] = "write"
    elif change == "oidc_build":
        jobs["build"]["permissions"]["id-token"] = "write"
    elif change in {"publisher_needs", "complete_needs"}:
        jobs["publish" if change == "publisher_needs" else "complete"].pop("needs")
    elif change == "tag_trigger":
        document["on"] = {"push": {"tags": ["v*"]}}
    elif change == "unprotected_ref":
        jobs["publish"]["steps"][0]["with"]["ref"] = "refs/heads/experimental"
    elif change == "clobber":
        jobs["attest"]["steps"][-1]["with"]["overwrite"] = True
    else:
        jobs["attest"]["steps"][4]["if"] = "false"
    assert publication_workflow_errors(yaml.safe_dump(document), kind=kind)
