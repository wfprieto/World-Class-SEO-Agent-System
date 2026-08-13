# Golden Demo

This is the fastest proof path for the public repository.

It demonstrates the working SEO audit system without API keys, paid tools, provider access, or live-site mutation.

## Run

```powershell
python -m seoctl.entrypoint audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output audit-runs/golden-demo --max-urls 20
```

## Expected Result

The command should complete with:

- status: `complete`
- evidence mode: `FIXTURE`
- pages crawled: `5`
- findings: `18`
- critical findings: `3`
- specialist agents executed: `7`
- external changes made: `NONE`
- unsupported material findings: `0`

## Expected Artifacts

The audit writes these files to the output directory:

- `run-manifest.json`
- `crawl.json`
- `findings.json`
- `decisions.json`
- `agent-contributions.json`
- `trust-summary.json`
- `technical-audit.md`
- `executive-summary.md`
- `remediation-plan.csv`
- `verification-plan.json`

## What To Inspect First

1. `executive-summary.md`: plain-English summary for non-technical readers.
2. `technical-audit.md`: technical findings and evidence.
3. `agent-contributions.json`: which specialist agents contributed.
4. `trust-summary.json`: evidence limits, unsupported findings, and mutation status.
5. `run-manifest.json`: artifact hashes and fixture/live-proof status.

## Safety Boundary

This demo is intentionally fixture-based. It proves routing, evidence handling, report generation, and multi-agent contribution tracking. It does not prove live rankings, live indexing, live Search Console, live analytics, live Core Web Vitals, or production provider connectivity.
