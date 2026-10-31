"""Canonical publication identities, final gates and bounded verification policy."""

from __future__ import annotations

REPOSITORY = "wfprieto/World-Class-SEO-Agent-System"
REPOSITORY_ID = 1288604237
OWNER_LOGIN = "wfprieto"
OWNER_ID = 283033906
VALIDATION_WORKFLOW_ID = 306847574
VALIDATION_WORKFLOW = ".github/workflows/validate.yml"
PREPARATION_WORKFLOW = ".github/workflows/prepare-publication.yml"
PUBLICATION_WORKFLOW = ".github/workflows/release.yml"
COMPARATOR_COMMIT = "6cf1ea9fe4c2088b2ad3089797f846850fd66164"

REQUIRED_GATES = {
    "phase4_deterministic", "phase5_deterministic", "phase6_artifact_consistency",
    "final_push_ci", "dependency_audit", "live_authorized_smokes", "seven_archetype_benchmark",
    "scrummaster3_verdict", "vp_engineering_verdict", "external_reproduction", "version_tag",
    "public_release_artifacts",
}
REVIEWERS = {
    "scrummaster3_verdict": ("final-scrummaster-3-verdict.json", "Senior ScrumMaster 3"),
    "vp_engineering_verdict": ("final-vp-engineering-verdict.json", "VP Engineering"),
}
REVIEW_ACTORS = {
    "scrummaster3_verdict": ("claude[bot]", 209825114),
    "vp_engineering_verdict": ("chatgpt-codex-connector[bot]", 199175422),
}
EXPECTED_CI_JOBS = frozenset({
    "provider-authentication", "validate", "quality_security_release",
    "phase0-rollback-certification", "phase-rollback-certification", "repository-certification",
    "clean wheel (ubuntu-latest, Python 3.13)", "clean wheel (windows-latest, Python 3.13)",
    *(f"validate ({platform}-latest, {version})"
      for platform in ("ubuntu", "windows") for version in ("3.11", "3.12", "3.13")),
})
EXECUTION_GATES = frozenset({
    "live_authorized_smokes", "seven_archetype_benchmark", "external_reproduction",
})
PREPARED_TTL_SECONDS = 86400
EVIDENCE_TTL_SECONDS = 604800
CLOCK_SKEW_SECONDS = 300
MAX_API_PAGES = 20
PAGE_SIZE = 100
MAX_API_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 40 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 1024
PROVENANCE_PREDICATE = "https://slsa.dev/provenance/v1"
SBOM_PREDICATE = "https://cyclonedx.org/bom"


def required_gate_values() -> dict[str, str]:
    """Preserve the existing final gate values, including actual role approvals."""
    return {gate: "APPROVE_GREAT" if gate in REVIEWERS else "PASS" for gate in REQUIRED_GATES}
