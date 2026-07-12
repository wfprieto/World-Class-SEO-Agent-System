# Product-Proof Skill Procedures

## product-proof-technical-audit
Canonical definition: `skills/product-proof-technical-audit.md`.
Execution boundary: Run one bounded canonical crawl dataset, apply only evidence-approved rules, record actual specialist contributions, produce client and engineering artifacts, and preserve every failed, missing, truncated, fixture, or approval-gated state.

## ai-retrieval-timeout-audit
Canonical definition: `skills/product-proof-technical-audit.md` and `knowledge/source-assets/ai-search-and-retrieval.md`.
Execution boundary: Analyze operator-supplied server logs only after recording the server or proxy stack. Treat 499 as nginx-family evidence, not a universal HTTP status. Do not infer citation exclusion from a timeout correlation.

## ai-citation-opportunity-map
Canonical definition: `knowledge/source-assets/ai-search-and-retrieval.md`.
Execution boundary: Use dated, platform-specific observations. Keep observed citations separate from proxy and modeled impact. Never claim a universal AI share-of-voice from an undated prompt sample.

## review-compliance-audit
Canonical definition: `knowledge/source-assets/local-reviews-compliance.md`.
Execution boundary: Screen operator-supplied practices and require platform/jurisdiction review. Do not provide legal conclusions or claim direct local-ranking causation.

## client-performance-narrative
Canonical definition: `knowledge/source-assets/client-reporting-roi.md`.
Execution boundary: A target may be described as exceeded only when it was recorded before the reporting period. Keep observed, proxy, and modeled value separate.
