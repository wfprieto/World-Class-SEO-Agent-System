"""Fixed execution-read selection and per-child token isolation, never evidence authority."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from scripts import publication_policy as policy

EXECUTION_TOKEN_ENV: Mapping[str, str] = MappingProxyType({
    "live_authorized_smokes": "PUBLICATION_LIVE_READ_TOKEN",
    "seven_archetype_benchmark": "PUBLICATION_BENCHMARK_READ_TOKEN",
    "external_reproduction": "PUBLICATION_REPRODUCTION_READ_TOKEN",
})
TOKEN_NAMES = frozenset((*EXECUTION_TOKEN_ENV.values(), "GH_TOKEN", "GITHUB_TOKEN",
                         "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"))


def primary_token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


def execution_token(gate: str, repository: str) -> str | None:
    if not isinstance(gate, str) or gate not in EXECUTION_TOKEN_ENV:
        raise ValueError("Unknown fixed execution-read gate")
    if (not isinstance(repository, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None
            or any(part in {".", ".."} for part in repository.split("/"))):
        raise ValueError("Execution-read repository is invalid")
    if repository == policy.REPOSITORY:
        return primary_token()
    token = os.environ.get(EXECUTION_TOKEN_ENV[gate])
    if token is None or not token.strip():
        raise ValueError("Explicit external execution-read credential is unavailable")
    return token


def child_environment(github_token: str | None = None) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key.upper() not in TOKEN_NAMES}
    if github_token is not None:
        if not isinstance(github_token, str) or not github_token.strip():
            raise ValueError("Selected GitHub credential is invalid")
        environment["GH_TOKEN"] = github_token
    environment.update(GH_HOST="github.com", GH_PROMPT_DISABLED="1")
    return environment


def _repository_get(args: list[str], repository: str) -> bool:
    if len(args) != 4 or args[:3] != ["api", "--hostname", "github.com"]:
        return False
    endpoint = args[3]
    prefix = "repos/" + repository
    path = endpoint.split("?", 1)[0]
    return (re.fullmatch(r"[A-Za-z0-9_./?=&-]+", endpoint) is not None
            and (path == prefix or path.startswith(prefix + "/"))
            and "//" not in path and not any(part in {".", ".."} for part in path.split("/")))


def _attestation_verify(args: list[str], repository: str) -> bool:
    if (len(args) != 18 or args[:2] != ["attestation", "verify"]
            or args[3:6] != ["--repo", repository, "--signer-workflow"]
            or args[7] != "--signer-digest" or args[9] != "--source-digest"
            or args[11] != "--source-ref" or args[13:15] != ["--deny-self-hosted-runners", "--predicate-type"]
            or args[16:] != ["--format", "json"]):
        return False
    return _attestation_values(args, repository)


def _attestation_values(args: list[str], repository: str) -> bool:
    path = Path(args[2])
    if (not path.is_absolute() or not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= policy.MAX_MEMBER_BYTES):
        return False
    return (re.fullmatch(re.escape(repository) + r"/\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", args[6]) is not None
            and re.fullmatch(r"[0-9a-f]{40}", args[8]) is not None and args[10] == args[8]
            and re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9_./-]+", args[12]) is not None
            and not any(part in {"", ".", ".."} for part in args[12].split("/"))
            and args[15] in {policy.PROVENANCE_PREDICATE, policy.SBOM_PREDICATE})


def readonly_operation(args: list[str], *, repository: str, body: bytes | None, limit: int) -> None:
    if (body is not None or not 0 < limit <= policy.MAX_ARCHIVE_BYTES
            or not (_repository_get(args, repository) or _attestation_verify(args, repository))):
        raise ValueError("Execution client permits only selected-repository GET and exact attestation verification")
