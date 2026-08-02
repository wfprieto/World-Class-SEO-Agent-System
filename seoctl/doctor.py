"""Deterministic, read-only local readiness diagnostics for ``seoctl``."""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from scripts.validate_architecture_contract import validate as validate_architecture
from scripts.validate_dependency_lock import validate as validate_dependency_lock
from scripts.validate_reference_freshness import validate as validate_references
from seoctl.registry import load_registry, validate_registry

SUPPORTED_PYTHON = {(3, 11), (3, 12), (3, 13)}
REQUIRED_ASSETS = (
    "governance/architecture-contract.json",
    "knowledge/reference-registry.json",
    "requirements-dev.in",
    "requirements-dev.txt",
    "schemas/agent-output.schema.json",
    "seoctl/command-registry.json",
)


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    status: str
    detail: str


def _check(identifier: str, errors: list[str], success: str) -> DoctorCheck:
    return DoctorCheck(
        id=identifier,
        status="PASS" if not errors else "FAIL",
        detail=success if not errors else "; ".join(sorted(errors)),
    )


def diagnose(
    root: Path,
    *,
    as_of: date | None = None,
    python_version: tuple[int, int] | None = None,
) -> dict[str, object]:
    """Return bounded static readiness without network, credentials, or mutation."""
    root = root.resolve()
    version = python_version or (sys.version_info.major, sys.version_info.minor)
    checks: list[DoctorCheck] = []
    checks.append(
        _check(
            "python.supported",
            [] if version in SUPPORTED_PYTHON else [f"unsupported Python {version[0]}.{version[1]}"],
            f"Python {version[0]}.{version[1]} is supported",
        )
    )
    missing = [relative for relative in REQUIRED_ASSETS if not (root / relative).is_file()]
    checks.append(_check("assets.required", missing, "required local assets are present"))

    try:
        registry_errors = validate_registry(load_registry(root / "seoctl/command-registry.json"))
    except (OSError, TypeError, ValueError) as exc:
        registry_errors = [f"registry unavailable: {exc}"]
    checks.append(_check("commands.registry", registry_errors, "command registry is coherent"))
    checks.append(
        _check(
            "architecture.static",
            validate_architecture(
                root,
                root / "governance/architecture-contract.json",
                root / "schemas/architecture-contract.schema.json",
            ),
            "bounded static architecture contract passes",
        )
    )
    checks.append(
        _check(
            "knowledge.provenance",
            validate_references(as_of=as_of, root=root),
            "per-pack knowledge provenance and freshness pass",
        )
    )
    checks.append(
        _check(
            "dependencies.lock",
            validate_dependency_lock(
                root / "requirements-dev.in", root / "requirements-dev.txt"
            ),
            "dependency inputs and hash lock agree",
        )
    )
    status = "PASS" if all(item.status == "PASS" for item in checks) else "FAIL"
    return {
        "status": status,
        "scope": "STATIC_LOCAL_ONLY",
        "network_performed": False,
        "provider_authentication_performed": False,
        "checks": [asdict(item) for item in checks],
        "limitations": [
            "Does not test live providers, credentials, deployments, rankings, traffic, or SEO outcomes.",
            "Static network inventory does not prove whole-program data flow or DNS pinning.",
        ],
    }
