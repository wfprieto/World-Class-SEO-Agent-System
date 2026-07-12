# Quality, Security, Observability, and Release Engineering

Phase 5 adds enforceable quality and software-supply-chain gates without making optional providers part of the core runtime.

## Local gates

```bash
ruff check . --select E9,F63,F7,F82
mypy runtime/telemetry.py runtime/run_budget.py runtime/tools.py scripts/scan_secrets.py scripts/generate_sbom.py scripts/generate_release_manifest.py scripts/validate_release_artifacts.py scripts/run_performance_benchmarks.py scripts/run_security_mutation_checks.py --ignore-missing-imports --check-untyped-defs
python scripts/scan_secrets.py
pytest -q --cov=runtime --cov=seoctl --cov=integrations --cov=adapters --cov-report=term-missing --cov-fail-under=65
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

The quality job enforces a 65 percent repository coverage floor while producing XML and JSON reports. It also applies correctness-critical Ruff rules and scoped mypy checks to the security, telemetry, and release surfaces. Higher category-specific coverage targets remain final-program release gates rather than invented claims.

## Release artifacts

SBOM, release manifest, coverage reports, JUnit, performance results, and build distributions are CI artifacts. They are generated from the exact checked-out commit and are not treated as a published release until Phase 6 release gates pass.

## Clean-install scope

CI builds a wheel in a fresh virtual environment and executes credential-free content and integration command families. Repository-context audits that load the full agent, workflow, knowledge, and template tree remain part of the Phase 6 release-candidate packaging gate.

## Network-dependent audit

`pip-audit` requires current vulnerability-service access. A local DNS or network failure is reported as `BLOCKED_BY_NETWORK`; GitHub Actions remains the authoritative dependency-audit environment.

## Rollback

Revert the Phase 5 commits. Telemetry is additive, generated artifacts are disposable, and no database migration or external provider action is introduced.
