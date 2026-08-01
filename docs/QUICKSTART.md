# Five-Minute Quick Start

## 1. Produce a deterministic flagship audit

```bash
python -m pip install -e .
seoctl --registry-check
seoctl audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output outputs/first-run --max-urls 20
```

This fixture command performs no live crawl. It writes the following reviewable files under the gitignored `outputs/first-run/` directory:

- `run-manifest.json` — inputs, limits, and the explicit `FIXTURE` evidence mode
- `technical-audit.md` — evidence-bound findings
- `executive-summary.md` — prioritized summary
- `remediation-plan.csv` — implementation backlog
- `verification-plan.json` — acceptance checks
- `agent-contributions.json` — recorded specialist decisions

Fixture output proves deterministic product behavior only. It is not evidence about the current state of `example.com` or any live website.

## 2. Discover commands and route work

```bash
seoctl --help
seoctl audit --help
seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
seoctl integrations list
seoctl benchmark compare
```

`system route` selects a workflow but does not run a live crawl. Root help is derived from the canonical command registry; family help shows the authoritative arguments for that family.

## 3. Run credential-free checks

```bash
seoctl content quality --input page.txt
seoctl schema validate --file schema.json
seoctl links profile --input backlinks.csv
seoctl drift baseline --url https://example.com --input page-state.json
```

These commands operate on supplied local evidence. Replace the illustrative filenames with files you are authorized to assess.

## 4. Preflight a live integration

```bash
seoctl integrations preflight --provider dataforseo
```

Preflight reports configuration; it is not proof that a metered provider call succeeded. Do not execute a live crawl or metered call until the target is authorized and the estimate and authorized ceiling are recorded. Remove credentials from the environment to disable an integration. Delete generated sidecars or local evidence only through the documented rollback path.
