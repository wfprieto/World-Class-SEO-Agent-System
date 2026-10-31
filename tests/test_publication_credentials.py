"""Synthetic-only token isolation: real child output contains booleans, not tokens."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts import publication_policy as policy
from scripts import publication_transport
from scripts.publication_transport import GitHubCLI, run_bounded

KEYS = ("PUBLICATION_LIVE_READ_TOKEN", "PUBLICATION_BENCHMARK_READ_TOKEN",
        "PUBLICATION_REPRODUCTION_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
        "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


@pytest.fixture(autouse=True)
def synthetic_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    for index, key in enumerate(KEYS):
        monkeypatch.setenv(key, f"synthetic-only-{index}")


def test_every_non_github_child_scrubs_all_publication_and_fallback_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index, key in enumerate(KEYS):
        monkeypatch.setenv(key, f"synthetic-only-{index}")
    code = ("import json,os;print(json.dumps({key:key in os.environ for key in "
            + repr(KEYS) + "}))")
    observed = json.loads(run_bounded([sys.executable, "-B", "-c", code], limit=2048, timeout=2))
    assert observed == dict.fromkeys(KEYS, False)


def test_selected_repository_metadata_get_is_allowed_with_only_its_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    def request(args: list[str], **kwargs: object) -> bytes:
        seen.append((args[1:], kwargs.get("github_token") == "synthetic-only-0"))
        return b'{}'

    monkeypatch.setattr(publication_transport, "run_bounded", request)
    selected = GitHubCLI(tmp_path, sys.executable).for_execution("live_authorized_smokes", "producer/project")
    assert selected.json("/repos/producer/project") == {}
    assert seen == [(["api", "--hostname", "github.com", "repos/producer/project"], True)]


@pytest.mark.parametrize("gate,index", [("live_authorized_smokes", 0),
    ("seven_archetype_benchmark", 1), ("external_reproduction", 2)])
def test_gate_selects_only_its_fixed_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                         gate: str, index: int) -> None:
    checks: list[bool] = []

    def request(args: list[str], **kwargs: object) -> bytes:
        token = kwargs.get("github_token")
        checks.append(token == f"synthetic-only-{index}" and token not in args)
        return b'{}'

    monkeypatch.setattr(publication_transport, "run_bounded", request)
    selected = GitHubCLI(tmp_path, sys.executable).for_execution(gate, "producer/project")
    selected.json("/repos/producer/project/actions/runs/1")
    assert checks == [True]


@pytest.mark.parametrize("gate,key", [("live_authorized_smokes", KEYS[0]),
    ("seven_archetype_benchmark", KEYS[1]), ("external_reproduction", KEYS[2])])
def test_external_missing_token_never_falls_back_to_primary_or_other_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate: str, key: str,
) -> None:
    monkeypatch.delenv(key)
    with pytest.raises(ValueError, match="unavailable"):
        GitHubCLI(tmp_path, sys.executable).for_execution(gate, "producer/project")


def test_primary_mutation_client_never_uses_a_foreign_token(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    checks: list[bool] = []

    def request(args: list[str], **kwargs: object) -> bytes:
        checks.append(kwargs.get("github_token") == "synthetic-only-3")
        return b'{}'

    monkeypatch.setattr(publication_transport, "run_bounded", request)
    base = GitHubCLI(tmp_path, sys.executable)
    base.for_execution("external_reproduction", "producer/project")
    base.write(f"/repos/{policy.REPOSITORY}/git/refs", {"ref": "synthetic"})
    base.for_execution("live_authorized_smokes", policy.REPOSITORY).json(f"/repos/{policy.REPOSITORY}")
    assert checks == [True, True]


@pytest.mark.parametrize("args", [
    ["api", "--hostname", "evil.invalid", "repos/producer/project/actions"],
    ["api", "--hostname", "github.com", "repos/other/project/actions"],
    ["api", "--hostname", "github.com", "repos/producer/project-evil/actions"],
    ["api", "--hostname", "github.com", "repos/producer/project/../other"],
    ["api", "--hostname", "github.com", "repos/producer/project/%2e%2e/other"],
    ["api", "--hostname", "github.com", "repos/producer/project/actions", "--method", "POST"],
    ["api", "--hostname", "github.com", "graphql", "--method", "POST"],
    ["release", "upload", "v1.0.0", "payload.json"], ["auth", "token"],
])
def test_readonly_client_denies_off_repo_mutation_and_arbitrary_commands(
    tmp_path: Path, args: list[str],
) -> None:
    selected = GitHubCLI(tmp_path, sys.executable).for_execution("live_authorized_smokes", "producer/project")
    with pytest.raises(ValueError, match="permits only"):
        selected.command(args)


def test_selected_client_cannot_write_or_reselect(tmp_path: Path) -> None:
    selected = GitHubCLI(tmp_path, sys.executable).for_execution("live_authorized_smokes", "producer/project")
    with pytest.raises(ValueError):
        selected.write("/repos/producer/project/git/refs", {"ref": "synthetic"})
    with pytest.raises(ValueError):
        selected.for_execution("external_reproduction", "other/project")


def test_exact_attestation_verification_is_allowed_but_extra_flags_are_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = tmp_path / "result.json"
    subject.write_bytes(b"synthetic")
    args = ["attestation", "verify", str(subject), "--repo", "producer/project",
            "--signer-workflow", "producer/project/.github/workflows/produce.yml",
            "--signer-digest", "a" * 40, "--source-digest", "a" * 40,
            "--source-ref", "refs/heads/main", "--deny-self-hosted-runners",
            "--predicate-type", policy.PROVENANCE_PREDICATE, "--format", "json"]
    monkeypatch.setattr(publication_transport, "run_bounded", lambda *a, **kw: b"[]")
    selected = GitHubCLI(tmp_path, sys.executable).for_execution("external_reproduction", "producer/project")
    assert selected.command(args) == b"[]"
    for changed in ([*args, "--hostname", "evil.invalid"], [*args[:13], *args[14:]],
                    [*args[:4], "other/project", *args[5:]]):
        with pytest.raises(ValueError):
            selected.command(changed)


def test_real_selected_child_receives_only_explicit_token_and_fixed_host() -> None:
    selected = "synthetic-selected-execution-only"
    digest = hashlib.sha256(selected.encode()).hexdigest()
    code = ("import hashlib,json,os;"
            "r={k:k in os.environ for k in " + repr(KEYS) + "};"
            "r['selected']=hashlib.sha256(os.environ.get('GH_TOKEN','').encode()).hexdigest()=="
            + repr(digest) + ";r['host']=os.environ.get('GH_HOST')=='github.com';print(json.dumps(r))")
    result = json.loads(run_bounded([sys.executable, "-B", "-c", code], limit=2048,
                                   github_token=selected, timeout=2))
    assert result == {**dict.fromkeys(KEYS, False), "GH_TOKEN": True, "selected": True, "host": True}


@pytest.mark.parametrize("fallback", [True, False])
def test_primary_explicit_fallback_or_local_auth_does_not_choose_gate_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fallback: bool,
) -> None:
    monkeypatch.delenv("GH_TOKEN")
    if not fallback:
        monkeypatch.delenv("GITHUB_TOKEN")
    checks: list[bool] = []

    def request(args: list[str], **kwargs: object) -> bytes:
        checks.append(kwargs.get("github_token") == ("synthetic-only-4" if fallback else None))
        return b'{}'

    monkeypatch.setattr(publication_transport, "run_bounded", request)
    GitHubCLI(tmp_path, sys.executable).for_execution(
        "external_reproduction", policy.REPOSITORY).json(f"/repos/{policy.REPOSITORY}")
    assert checks == [True]


@pytest.mark.parametrize("gate,repository", [("user-selected-env", "producer/project"),
    ("live_authorized_smokes", "../project"), ("live_authorized_smokes", "https://github.com/a/b")])
def test_gate_names_and_repository_paths_are_fixed_not_wire_chosen(
    tmp_path: Path, gate: str, repository: str,
) -> None:
    with pytest.raises(ValueError):
        GitHubCLI(tmp_path, sys.executable).for_execution(gate, repository)


def test_new_repository_metadata_read_does_not_enable_descriptor_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publication_transport, "run_bounded", lambda *args, **kwargs: b'{}')
    with pytest.raises(ValueError):
        GitHubCLI(tmp_path, sys.executable).write(f"/repos/{policy.REPOSITORY}",
                                                {"name": "synthetic"}, method="PATCH")
