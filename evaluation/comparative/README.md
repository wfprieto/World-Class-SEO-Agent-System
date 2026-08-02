# Comparative Evaluation

This directory is the canonical, machine-readable comparison between the World-Class SEO Agent System and a pinned external comparator.

## Files

- `world-class-baseline.json`: current target score and evidence.
- `claude-seo-baseline.json`: pinned comparator score and evidence.
- `capability-parity.json`: capability-by-capability gap and disposition ledger.
- `scorecard.schema.json`: immutable scorecard shape.

## Rules

1. The comparator commit is pinned for an improvement cycle.
2. Scores use `sum((score / 10) * weight)` and category weights total 100.
3. Evidence maturity limits the maximum score.
4. File count is not capability maturity.
5. A closed capability requires linked evidence.
6. A `GAP_OPEN` row requires a target PR and acceptance criteria.
7. Final release validation permits no open capability row.
8. External facts must name their repository source and pinned commit.
9. Documentation, mocks and fixtures cannot independently prove production readiness.
10. The scoring schema may change only through a separately reviewed methodology migration with before-and-after results.
11. Target baselines must identify a commit reachable from current `HEAD` and pin canonical hashes of the effective merged command and capability inventories; every supported semantic overlay mutation fails validation, including schema-version and unknown-field changes, while JSON formatting, key order, and unrelated files do not.
12. Code verification, authorized live verification, and external reproduction are independent evidence tiers.
13. A rebaseline may correct stale capability facts without inventing a new numerical score; rescoring requires a separately reviewed evidence package.

The command hash merges `seoctl/command-registry.json` with `seoctl/command-registry-overlay.json`. The capability hash merges `orchestration/capability-registry.json` with `orchestration/product-proof-capability-overlay.json` using additive runtime list semantics. Both overlays require schema version `1.1.0` and reject unknown top-level fields so unmodeled semantic metadata cannot bypass freshness checks.

Run locally:

```bash
python scripts/inventory_comparator.py
pytest -q tests/test_comparative_rebaseline.py
```
