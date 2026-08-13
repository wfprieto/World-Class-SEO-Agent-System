# Bad SEO Fixture Pack

This pack provides deterministic, credential-free SEO failure cases for audit tests and demonstrations.
It is synthetic and must not be described as live production evidence.

Canonical fixture file:

`examples/bad-seo-fixtures/fixtures.json`

## Coverage

- `head-tags`: missing titles and duplicated descriptions.
- `content`: thin, generic public copy without information gain.
- `indexability`: conflicting noindex, canonical, and sitemap signals.
- `http-status`: soft-404 behavior that remains indexable.
- `redirects`: loop and chain risk.
- `structure`: commercial orphan pages.
- `performance`: Core Web Vitals composite failure.
- `compound`: multi-signal template failure.

## Expected Finding Contract

Every fixture must include:

- `id`
- `category`
- `url`
- `inputs`
- `expected_findings`

Every expected finding must include:

- `id`
- `severity`
- `evidence_refs`
- `recommended_action_category`

Allowed severities are `Critical`, `High`, `Medium`, and `Low`.

## Agent Use

- SEO Technical Agent uses these fixtures to test crawl, indexing, metadata, performance, and redirect reasoning.
- SEO Full Audit/Analyst Agent uses them to verify finding severity and evidence references.
- Senior SEO Engineer Agent uses them to turn expected findings into implementation tasks.
- SEO Output Report Agent uses them to practice plain-language explanations without claiming live proof.

## Guardrails

- Do not use these fixtures as a replacement for a real crawl, GSC export, log file, or field data.
- Do not add client domains, private URLs, credentials, or identifiable production data.
- Keep every expected finding evidence-bound and deterministic.
