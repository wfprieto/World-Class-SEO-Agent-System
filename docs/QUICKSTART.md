# Five-Minute Quick Start

## 1. Produce the deterministic flagship evidence package

```bash
python -m pip install -e .
seoctl --registry-check
seoctl system doctor
seoctl audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output outputs/first-run --max-urls 20
```

The doctor performs bounded static checks only and makes no network or provider-authentication call. A pass means the local repository contracts are coherent; it does not certify a live provider, deployment, website, ranking, traffic, or conversion result.

`seoctl audit technical` is the sole flagship command. This fixture command performs no live crawl and writes a decision-ready technical SEO evidence package containing exactly these ten reviewable files under the gitignored `outputs/first-run/` directory:

- `crawl.json` — normalized bounded crawl evidence
- `findings.json` — consolidated evidence-bound findings
- `decisions.json` — recorded governance decisions
- `agent-contributions.json` — recorded specialist and governance contributions
- `trust-summary.json` — attempted, completed, failed, and unsupported states
- `technical-audit.md` — evidence-bound findings
- `executive-summary.md` — prioritized summary
- `remediation-plan.csv` — implementation backlog
- `verification-plan.json` — acceptance checks
- `run-manifest.json` — inputs, limits, and the explicit `FIXTURE` evidence mode

Fixture output proves deterministic contract behavior only. It is not evidence about the current state of `example.com` or any live website. A bounded live run reports observations from an authorized target at a stated time. Neither mode proves complete site coverage, search-engine indexing, ranking, traffic, conversion, production readiness, or comparative superiority, and the command makes no external change.

## 2. Discover commands and route work

```bash
seoctl --help
seoctl audit --help
seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
seoctl integrations list
seoctl benchmark compare
```

`system route` selects a workflow but does not run a live crawl. Root help is derived from the canonical command registry; family help shows the authoritative arguments for that family.

`system.run` and `full-site-audit` are evidence-dependent multi-agent orchestration capabilities. They are not flagship commands and cannot claim complete coverage when required evidence or specialist execution is missing.

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
