from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import seoctl.registry as command_registry
from integrations.product_proof.service import ARTIFACT_FILENAMES
from scripts import validate_product_contract as validator
from scripts.generate_capability_evidence_registry import build

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.fixture
def contract_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal independent repository with base-plus-overlay capabilities."""
    repo = tmp_path / "repo"
    for relative in (
        "governance",
        "schemas",
        "seoctl",
        "orchestration",
        "skills",
        "agents",
        "knowledge",
        "docs",
        "tests",
        "integrations/product_proof",
    ):
        (repo / relative).mkdir(parents=True, exist_ok=True)

    shutil.copyfile(
        ROOT / "schemas/product-contract.schema.json",
        repo / "schemas/product-contract.schema.json",
    )
    shutil.copyfile(
        ROOT / "schemas/capability-certification.schema.json",
        repo / "schemas/capability-certification.schema.json",
    )
    shutil.copyfile(
        ROOT / "schemas/capability-certification-receipt.schema.json",
        repo / "schemas/capability-certification-receipt.schema.json",
    )
    (repo / "knowledge/seo-quality-gates.md").write_text("# Gates\n", encoding="utf-8")
    (repo / "integrations/product_proof/service.py").write_text(
        "ARTIFACT_FILENAMES = " + repr(dict(ARTIFACT_FILENAMES)) + "\n",
        encoding="utf-8",
    )
    (repo / "agents/audit.md").write_text("# Audit agent\n", encoding="utf-8")
    (repo / "skills/deep-skill-procedures.md").write_text(
        "## runtime-context\nContext.\n\n"
        "## product-proof-technical-audit\nAudit.\n\n"
        "## documented-only\nDocumentation.\n",
        encoding="utf-8",
    )
    for relative in (
        "tests/test_seoctl.py",
        "tests/test_seoctl_entrypoint.py",
        "tests/test_phase4_skills_and_references.py",
        "tests/test_product_proof_technical_audit.py",
    ):
        (repo / relative).write_text("# evidence\n", encoding="utf-8")

    _write_json(
        repo / "seoctl/command-registry.json",
        {
            "version": "1.0.0",
            "commands": [
                {
                    "id": "system.run",
                    "path": ["system", "run"],
                    "handler": "system_run",
                    "owner": "Audit Agent",
                    "skills": ["runtime-context"],
                    "execution_class": "executable",
                    "network": "provider_optional",
                }
            ],
            "agents": {
                "Audit Agent": {
                    "execution_class": "executable",
                    "commands": ["system.run"],
                }
            },
        },
    )
    _write_json(
        repo / "seoctl/command-registry-overlay.json",
        {
            "version": "1.1.0",
            "commands": [
                {
                    "id": "audit.technical",
                    "path": ["audit", "technical"],
                    "handler": "audit_technical",
                    "owner": "Audit Agent",
                    "skills": ["product-proof-technical-audit"],
                    "execution_class": "executable",
                    "network": "live_optional",
                }
            ],
            "agent_commands": {"Audit Agent": ["audit.technical"]},
            "agent_execution_classes": {},
        },
    )
    _write_json(
        repo / "orchestration/capability-registry.json",
        {
            "shared": {},
            "agents": {
                "Audit Agent": {
                    "agent_file": "agents/audit.md",
                    "skills": ["runtime-context"],
                    "skill_files": [],
                    "knowledge_files": [],
                    "templates": [],
                    "required_evidence": [],
                }
            },
        },
    )
    _write_json(
        repo / "orchestration/product-proof-capability-overlay.json",
        {
            "shared_knowledge_files": [],
            "agent_overrides": {
                "Audit Agent": {"skills": ["product-proof-technical-audit"]}
            },
        },
    )
    _write_json(
        repo / "skills/package-registry.json",
        {"package_document": "", "packages": {}},
    )
    _write_json(
        repo / "skills/skill-catalog.json",
        {
            "version": "1.0.0",
            "categories": [
                {
                    "name": "Test capabilities",
                    "skills": [
                        "runtime-context",
                        "product-proof-technical-audit",
                        "documented-only",
                    ],
                }
            ],
        },
    )
    _write_json(
        repo / "governance/capability-certification.json",
        {
            "$schema": "../schemas/capability-certification.schema.json",
            "schema_version": "1.0.0",
            "max_receipt_age_days": 30,
            "required_checks": [
                "prerequisites", "auth_preflight", "fixture_replay",
                "adverse_cases", "live_probe", "redaction",
            ],
            "trusted_issuers": [],
            "profiles": [
                {
                    "id": "fixture-live-profile",
                    "version": 1,
                    "capabilities": ["system.run", "audit.technical"],
                    "provider_id": "fixture-provider",
                    "provider": "fixture provider",
                    "transport": "bounded_https",
                    "side_effect": "read_only",
                    "owner": "Audit Agent",
                    "relevant_sources": ["integrations/product_proof/service.py"],
                    "credential_env_sets": [],
                    "required_binaries": [],
                    "live_authorization": {
                        "execute_flag": "--execute-live",
                        "confirmation": "LIVE_CERTIFY",
                        "authorized_target_required": True,
                        "cost_approval_required": False,
                        "write_approval_required": False,
                    },
                }
            ],
        },
    )

    contract = {
        "$schema": "../schemas/product-contract.schema.json",
        "schema_version": "1.0.0",
        "contract_id": "world-class-seo-product",
        "product_name": "World-Class SEO Agent System",
        "product_category": "model-agnostic, evidence-governed SEO operating system",
        "layer_model": {"primary": "documentation", "executable": "bounded CLI"},
        "primary_operator": "technical SEO practitioner or SEO engineer",
        "secondary_users": ["SEO teams"],
        "flagship": {
            "command_id": "audit.technical",
            "command": "seoctl audit technical",
            "skill": "product-proof-technical-audit",
            "owner": "Audit Agent",
            "mode": "bounded read-only diagnosis",
            "outcome": "decision-ready technical SEO evidence package",
            "artifacts": list(ARTIFACT_FILENAMES.values()),
        },
        "non_flagship_capabilities": {
            "system.run": "evidence-dependent orchestration",
            "full-site-audit": "broad synthesis",
        },
        "proof_boundaries": {
            "fixture": "deterministic behavior only",
            "live_bounded": "authorized observations only",
            "never_implies": ["production readiness"],
            "external_changes": False,
        },
        "claim_language_policy": {
            "brand_name_only": "World-Class SEO Agent System",
            "prohibited_patterns": [
                r"\bmost effective\b",
                r"\bproduction[- ]ready\b",
                r"\bproven superior\b",
            ],
        },
        "capability_classification": {
            "command_network_proof": {
                "none": "LOCAL_DETERMINISTIC",
                "live_optional": "LIVE_BOUNDED",
                "provider_optional": "PROVIDER_OR_FIXTURE",
            },
            "agent_execution_proof": {
                "executable": "COMMAND_BACKED",
                "advisory": "DOCUMENTED_ADVISORY",
                "governance": "GOVERNANCE_CONTROL",
            },
        },
        "authoritative_surfaces": [
            {
                "path": "README.md",
                "required_terms": [
                    "model-agnostic, evidence-governed SEO operating system",
                    "technical SEO practitioner or SEO engineer",
                    "decision-ready technical SEO evidence package",
                ],
            },
            {
                "path": "SYSTEM_SPEC.md",
                "required_terms": [
                    "model-agnostic, evidence-governed SEO operating system",
                    "technical SEO practitioner or SEO engineer",
                ],
            },
            {
                "path": "pyproject.toml",
                "required_terms": [
                    "model-agnostic, evidence-governed SEO operating system"
                ],
            },
            {
                "path": "docs/QUICKSTART.md",
                "required_terms": [
                    "seoctl audit technical",
                    "decision-ready technical SEO evidence package",
                ],
            },
            {
                "path": "skills/product-proof-technical-audit.md",
                "required_terms": ["decision-ready technical SEO evidence package"],
            },
        ],
    }
    _write_json(repo / validator.CONTRACT_PATH, contract)
    for row in contract["authoritative_surfaces"]:
        path = repo / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(row["required_terms"]), encoding="utf-8")

    monkeypatch.setattr(command_registry, "REGISTRY_PATH", repo / "seoctl/command-registry.json")
    monkeypatch.setattr(
        command_registry,
        "OVERLAY_PATH",
        repo / "seoctl/command-registry-overlay.json",
    )
    _write_json(repo / validator.EVIDENCE_PATH, build(repo))
    return repo


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_self_consistent_evidence(
    repo: Path, monkeypatch: pytest.MonkeyPatch, evidence: dict[str, Any]
) -> None:
    _write_json(repo / validator.EVIDENCE_PATH, evidence)
    monkeypatch.setattr(validator, "build_evidence_registry", lambda _root: evidence)


def test_minimal_canonical_contract_passes(contract_repo: Path) -> None:
    assert validator.validate(contract_repo) == []


def test_contract_schema_rejects_unknown_fields(contract_repo: Path) -> None:
    contract_path = contract_repo / validator.CONTRACT_PATH
    contract = _read_json(contract_path)
    contract["unsupported_claim"] = "best in the world"
    _write_json(contract_path, contract)

    errors = validator.validate(contract_repo)

    assert len(errors) == 1
    assert errors[0].startswith("product contract schema validation failed:")


def test_authority_surface_requires_every_canonical_term(contract_repo: Path) -> None:
    (contract_repo / "README.md").write_text(
        "model-agnostic, evidence-governed SEO operating system\n"
        "technical SEO practitioner or SEO engineer\n",
        encoding="utf-8",
    )

    assert validator.validate(contract_repo) == [
        "README.md is missing canonical product term: "
        "decision-ready technical SEO evidence package"
    ]


@pytest.mark.parametrize("surface", sorted(validator.EXPECTED_AUTHORITIES))
def test_every_authority_rejects_blocked_maturity_wording(
    contract_repo: Path, surface: str
) -> None:
    path = contract_repo / surface
    path.write_text(path.read_text(encoding="utf-8") + "\nProduction ready.\n", encoding="utf-8")

    errors = validator.validate(contract_repo)

    assert errors == [
        f"{surface} contains prohibited product wording matched by "
        "'\\\\bproduction[- ]ready\\\\b': 'Production ready'"
    ]


def test_overlay_command_is_part_of_effective_inventory(contract_repo: Path) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    assert "audit.technical" in evidence["commands"]

    overlay_path = contract_repo / "seoctl/command-registry-overlay.json"
    overlay = _read_json(overlay_path)
    overlay["commands"][0]["network"] = "none"
    _write_json(overlay_path, overlay)

    errors = validator.validate(contract_repo)

    assert any(
        "capability evidence registry" in error
        and ("stale" in error or "profile coverage mismatch" in error)
        for error in errors
    )


def test_classification_requires_all_evidence_classes(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    command = evidence["commands"]["system.run"]
    del command["evidence"]["CI"]
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    errors = validator.validate(contract_repo)

    assert len(errors) == 1
    assert errors[0].startswith(
        "commands system.run has incomplete evidence-class coverage"
    )


def test_pass_classification_requires_at_least_one_reference(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    evidence["commands"]["system.run"]["evidence"]["SOURCE"] = {
        "status": "PASS",
        "refs": [],
    }
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    assert validator.validate(contract_repo) == [
        "commands system.run SOURCE PASS has no references"
    ]


def test_live_verified_requires_provider_pass(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    evidence["commands"]["audit.technical"]["claim_ceiling"] = "LIVE_VERIFIED"
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    assert validator.validate(contract_repo) == [
        "commands audit.technical claims LIVE_VERIFIED without provider evidence"
    ]


def test_local_test_reference_cannot_masquerade_as_live_provider_proof(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    command = evidence["commands"]["audit.technical"]
    command["claim_ceiling"] = "LIVE_VERIFIED"
    command["evidence"]["PROVIDER"] = {
        "status": "PASS",
        "refs": ["tests/test_seoctl.py"],
    }
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    errors = validator.validate(contract_repo)

    assert any(
        "audit.technical" in error
        and "PROVIDER" in error
        and "provider" in error.lower()
        for error in errors
    )


def test_legacy_five_field_provider_receipt_cannot_promote_live_verified(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt_path = contract_repo / "evaluation/provider-receipts/audit-technical.json"
    _write_json(
        receipt_path,
        {
            "schema_version": "1.0.0",
            "evidence_class": "PROVIDER",
            "status": "PASS",
            "provider": "authorized-site-observation",
            "observed_at": "2026-08-02T12:00:00Z",
            "capability": {"kind": "commands", "id": "audit.technical"},
        },
    )
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    command = evidence["commands"]["audit.technical"]
    command["claim_ceiling"] = "LIVE_VERIFIED"
    command["evidence"]["PROVIDER"] = {
        "status": "PASS",
        "refs": ["evaluation/provider-receipts/audit-technical.json"],
    }
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    errors = validator.validate(contract_repo)
    assert any("invalid PROVIDER provenance" in error for error in errors)


def test_documented_only_capability_cannot_be_promoted(
    contract_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _read_json(contract_repo / validator.EVIDENCE_PATH)
    documented = evidence["skills"]["documented-only"]
    assert documented["delivery_state"] == "DOCUMENTED_ONLY"
    documented["claim_ceiling"] = "REGISTRY_VERIFIED"
    _write_self_consistent_evidence(contract_repo, monkeypatch, evidence)

    errors = validator.validate(contract_repo)

    assert "skills documented-only promotes a documented-only capability" in errors


def test_flagship_artifact_contract_is_exactly_the_runtime_ten(
    contract_repo: Path,
) -> None:
    expected = {
        "crawl.json",
        "findings.json",
        "decisions.json",
        "agent-contributions.json",
        "trust-summary.json",
        "technical-audit.md",
        "executive-summary.md",
        "remediation-plan.csv",
        "verification-plan.json",
        "run-manifest.json",
    }
    assert len(ARTIFACT_FILENAMES) == 10
    assert set(ARTIFACT_FILENAMES.values()) == expected

    contract_path = contract_repo / validator.CONTRACT_PATH
    contract = _read_json(contract_path)
    contract["flagship"]["artifacts"].remove("trust-summary.json")
    _write_json(contract_path, contract)

    assert validator.validate(contract_repo) == [
        "flagship artifact inventory disagrees with runtime ARTIFACT_FILENAMES"
    ]


def test_flagship_owner_and_skill_must_match_effective_command(
    contract_repo: Path,
) -> None:
    contract_path = contract_repo / validator.CONTRACT_PATH
    contract = _read_json(contract_path)
    contract["flagship"]["owner"] = "Unregistered Owner"
    _write_json(contract_path, contract)

    assert validator.validate(contract_repo) == [
        "flagship owner or skill disagrees with the effective command registry"
    ]
