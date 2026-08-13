# Releasing

Public releases are fail-closed. A maintainer may create and push an exact semantic tag only after `evaluation/comparative/final-release-readiness.json` records `APPROVED` and every required gate records `PASS` or `APPROVE_GREAT`.

Before tagging, run the repository certification workflow on the exact commit and confirm both independent reviewer verdicts, authorized live-site evidence, clean external reproduction, and current comparative evidence. Then verify version consistency:

```powershell
python scripts/validate_phase6_readiness.py
python scripts/validate_release_version.py
```

The tag-triggered release workflow repeats the fail-closed gates, builds and clean-installs the wheel, generates a CycloneDX SBOM and hashed release manifest, writes SHA-256 checksums, creates GitHub build and SBOM attestations, and publishes those assets with the GitHub release. A blocked readiness decision prevents publication.

Consumers can verify a downloaded artifact with:

```powershell
Get-FileHash .\world_class_seo_agent_system-*.whl -Algorithm SHA256
gh attestation verify .\world_class_seo_agent_system-*.whl -R wfprieto/World-Class-SEO-Agent-System
```

Rollback is release-specific: preserve the failed tag and evidence, identify the last verified release, publish a corrected version rather than replacing immutable artifacts, and update the support declaration in `SECURITY.md`.
