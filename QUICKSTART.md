# Quickstart

Use this path to prove the repository works without API keys, paid tools, or live-site access.

## 1. Install

```powershell
python -m pip install -e .[dev]
```

If your shell does not support extras syntax, use:

```powershell
python -m pip install -e .
python -m pip install -r requirements-dev.txt
```

## 2. Run The Golden Demo Audit

```powershell
python -m seoctl.entrypoint audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output audit-runs/golden-demo --max-urls 20
```

This is an offline fixture run. It proves command routing, deterministic audit logic, evidence recording, report generation, and agent contribution tracking. It does not claim live rankings, live indexing, live Core Web Vitals, or live provider access.

## 3. Inspect The Output

The command writes:

- `audit-runs/golden-demo/run-manifest.json`
- `audit-runs/golden-demo/findings.json`
- `audit-runs/golden-demo/technical-audit.md`
- `audit-runs/golden-demo/executive-summary.md`
- `audit-runs/golden-demo/remediation-plan.csv`
- `audit-runs/golden-demo/verification-plan.json`
- `audit-runs/golden-demo/agent-contributions.json`
- `audit-runs/golden-demo/trust-summary.json`

Start with `executive-summary.md` for the plain-English result, then inspect `run-manifest.json` and `agent-contributions.json` to see how the system ties findings to evidence and specialist agent work.

## 4. Validate The Repository

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate-repository.ps1
python -m pytest -q --basetemp .pytest_tmp
python -m ruff check . --select E9,F63,F7,F82 --no-cache
python -m mypy runtime seoctl integrations adapters scripts
python scripts\scan_secrets.py
```

On Windows, `--basetemp .pytest_tmp` avoids local user-temp permission problems and keeps test output inside the repository workspace.

## 5. What This Proves

- The CLI routes a technical SEO audit request.
- The product-proof audit service runs from safe fixtures.
- The system generates evidence-backed artifacts.
- The report layer stays explicit about fixture limitations.
- No external site or provider is changed.
- No secrets are required.

## 6. What This Does Not Prove

- It does not prove live rankings.
- It does not prove live indexing.
- It does not prove live Search Console, GA4, PageSpeed, or CrUX connectivity.
- It does not authorize automatic SEO changes.
- It does not replace a production deployment gate.

Use this quickstart as the public proof path before moving into live adapters, private SaaS deployment, or approval-gated autonomous SEO actions.
