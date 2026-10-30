# Releasing

Public releases are fail-closed. A maintainer may create and push an exact semantic tag only after `evaluation/comparative/final-release-readiness.json` records `APPROVED` and every required gate records `PASS` or `APPROVE_GREAT`.

Before tagging, run the repository certification workflow on the exact commit and confirm both independent reviewer verdicts, authorized live-site evidence, clean external reproduction, and current comparative evidence. Then verify version consistency:

```powershell
python scripts/validate_phase6_readiness.py
python scripts/validate_release_version.py
```

The tag-triggered release workflow repeats the fail-closed gates, builds and clean-installs the wheel, generates a CycloneDX SBOM and hashed release manifest, writes SHA-256 checksums, creates GitHub build and SBOM attestations, and publishes those assets with the GitHub release. A blocked readiness decision prevents publication.

Readiness retains all twelve canonical gate identities; absent, empty, unknown, or
partial gate maps cannot authorize publication. APPROVED also requires actual
candidate-bound final reviewer approvals, complete code/live/external verification
states, candidate-bound CI metadata, and passed benchmark execution evidence.
`verification_evidence` must contain `live_authorized_smokes` and
`external_reproduction`, each with `state: "PASS"`, the exact `candidate_commit`,
and nonempty `evidence_refs` using repository-file SHA-256 and bound-commit records.
Those files must exist unchanged at the approved candidate. Gate labels cannot
override contradictory files. The current BLOCKED decision remains truthful and
does not authorize publication.

Source-integrity proofs authenticate executable matching-source `__pycache__`
payloads in candidate and restored-baseline modes against trusted compiler output.
Cache headers/source hashes alone are not authority, and `-B` disables writes,
not reads. Cache bytes are never unmarshaled. Normal compileall caches support
optimization levels 0/1/2, canonical absolute or repository-relative filenames,
normal slash variants, and normal leading-dot paths. Custom `compileall -d/-s/-p`
filenames, unknown cache names/tags, and unauthenticated payloads fail closed.
Use a source-only checkout or explicitly regenerate normal caches; the validator
does not silently delete files or grant cache exceptions.
Orphan and importable cache-directory impostors in certified repository roots are
rejected, including `security` and `contracts`. Recognized dependency caches
outside those roots, such as ignored `.venv` files, are not source-certified;
dependency/toolchain trust remains a separate gate. Every cache matching tracked
repository source is authenticated regardless of its directory.

Consumers can verify a downloaded artifact with:

```powershell
Get-FileHash .\world_class_seo_agent_system-*.whl -Algorithm SHA256
gh attestation verify .\world_class_seo_agent_system-*.whl -R wfprieto/World-Class-SEO-Agent-System
```

Rollback is release-specific: preserve the failed tag and evidence, identify the last verified release, publish a corrected version rather than replacing immutable artifacts, and update the support declaration in `SECURITY.md`.
