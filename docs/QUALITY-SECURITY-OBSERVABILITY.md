# Quality, Security, Observability, and Release Engineering

The repository uses enforceable, non-regression quality and software-supply-chain gates without making optional providers part of the core runtime.

## Local gates

```bash
python scripts/validate_architecture_contract.py
python scripts/validate_quality_ratchets.py
ruff check runtime adapters integrations seoctl scripts
mypy runtime seoctl integrations adapters
python scripts/scan_secrets.py
pytest -q --cov=runtime --cov=seoctl --cov=integrations --cov=adapters --cov-report=term-missing --cov-fail-under=78
pip-audit -r requirements-dev.txt --desc off
python scripts/generate_sbom.py --out outputs/sbom.cdx.json
python scripts/generate_release_manifest.py --sbom outputs/sbom.cdx.json --out outputs/release-manifest.json
python scripts/validate_release_artifacts.py --manifest outputs/release-manifest.json --sbom outputs/sbom.cdx.json
python scripts/run_performance_benchmarks.py --out outputs/performance.json
python scripts/run_security_mutation_checks.py
python -m build
```

## Telemetry boundary

Tool telemetry records operation, duration, request count, retry count, units, estimated cost, status, and redacted metadata. It never stores credential values, request bodies containing secrets, or user-level analytics identifiers. Telemetry is bounded to a configured maximum number of in-memory events and does not replace the canonical evidence store.

## Coverage and quality scope

The quality job enforces a 78 percent repository branch-coverage floor while producing XML and JSON reports. Critical runtime, persistence, provider, and network files have separate non-regression floors. These floors prevent loss; they are not claims that every lower-covered path is sufficiently tested.

Ruff evaluates `E4`, `E7`, `E9`, `F`, `I`, `B`, `UP`, `C4`, `SIM`, and `C90`. Existing findings are fingerprinted in the machine ratchet; any new fingerprint, increased count, or stale baseline fails. Mypy follows imported bodies normally, while the AST ratchet prevents any new unannotated function and freezes exact legacy annotation ceilings. New files default to 400 lines, new functions to 75 lines and complexity 15, with complete annotations required.

## Release artifacts

SBOM, release manifest, coverage reports, JUnit, performance results, and build distributions are CI artifacts. They are generated from the exact checked-out commit and are not treated as a published release until Phase 6 release gates pass.

## Clean-install scope

CI builds a wheel in a fresh virtual environment and executes credential-free content and integration command families. Repository-context audits that load the full agent, workflow, knowledge, and template tree remain part of the Phase 6 release-candidate packaging gate.

## Network-dependent audit

`pip-audit` requires current vulnerability-service access. A local DNS or network failure is reported as `BLOCKED_BY_NETWORK`; GitHub Actions remains the authoritative dependency-audit environment.

## Rollback

Revert the bounded quality-contract commits. Generated baselines and CI artifacts are disposable, and no database migration or external provider action is introduced.
