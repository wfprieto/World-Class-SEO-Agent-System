# Product-Proof Technical Audit

## Goal

Provide one command that a new operator can run against an authorized public target to produce a bounded technical audit and client-ready artifacts:

```bash
seoctl audit technical \
  --url https://example.com \
  --output audit-runs/example-com
```

For deterministic testing without a network:

```bash
seoctl audit technical \
  --url https://example.com \
  --fixture tests/fixtures/product-proof-site.json \
  --output audit-runs/fixture
```

Fixture success validates the contract only. It is not evidence that live crawling, search-engine access, analytics, provider APIs, or business outcomes worked.

## Default bounds

- 500 URLs
- Depth 6
- 10 discovered asset hostnames
- 10 redirect hops per request
- 30-second request timeout
- 12 MB per response

An operator can lower or raise URL, depth, and asset-host ceilings within hard limits. A bounded crawl does not claim complete coverage.

## Participating roles

The command records actual deterministic contributions from:

1. SEO Diagnostic Infrastructure Agent
2. SEO Technical Agent
3. SEO Information Architecture Agent
4. SEO Compliance & Legal Agent
5. SEO Full Audit/Analyst Agent
6. SEO Scrummaster Agent
7. SEO Output Report Agent

Agent contribution records show evidence added, findings proposed and accepted, decisions recorded, and each role's unique contribution. This is not a claim that seven separate language-model calls occurred.

## Evidence behavior

- Rules cite `knowledge/seo-claim-registry.json`.
- Primary-source corrections override conflicting secondary guidance.
- Unverified and disputed claims cannot create verified recommendations.
- Missing or truncated evidence stays visible.
- No external mutation is performed.
- Search-engine indexing, ranking, traffic, conversion, and revenue are not inferred from crawl evidence.

## High-value checks

- robots.txt status and rules on the primary and asset hosts
- unreadable noindex or canonical instructions caused by crawl blocking
- server errors, missing pages, and soft 404s
- internal redirects
- canonical cycles, chains, invalid targets, and contradictory internal links
- pagination canonicals and crawlable sequence links
- faceted-navigation duplicate space and empty successful pages
- AI extraction-control trade-offs
- likely lazy-loaded early images and missing layout dimensions
- crawl-budget materiality gate

## Client deliverables

The executive summary explains impact and action without exposing internal runtime jargon. The engineering report retains claim IDs, evidence classes, affected scope, owners, and verification steps. The trust summary states exactly what ran and what did not.

## Supporting intelligence commands

These commands require operator-supplied evidence and do not make live platform claims:

```bash
seoctl intelligence ai-timeouts --log access.log --server-stack nginx
seoctl intelligence ai-citations --observations ai-observations.json
seoctl intelligence review-compliance --input review-practices.json
seoctl intelligence performance-narrative --input performance.json
```

- AI timeout analysis records server-stack limitations and user-agent spoofing risk.
- Citation opportunities require dated, platform-specific observations.
- Review screening requires platform and jurisdiction review and is not legal advice.
- Performance narration preserves whether the target was actually established before the period and keeps observed, proxy, and modeled value separate.

## Installed-wheel assets

The package includes runtime agents, skills, knowledge, prompts, schemas, templates, workflows, and product-proof evaluation assets under the installed environment's `share/world-class-seo` directory. Runtime resolution prefers an explicit `WORLD_CLASS_SEO_ROOT`, then a valid source checkout, then the installed share directory.
