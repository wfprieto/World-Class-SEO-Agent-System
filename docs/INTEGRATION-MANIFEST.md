# Integration Record

**Status:** Integrated into `main`  
**Version:** 1.5.0  
**Last reviewed:** 2026-07-10

This records the capabilities added in v1.5.0 and how they are wired into the system. These files are part of the repository, not a separate drop-in kit. For the running history, see `CHANGELOG.md`.

## What was added and where it lives

| Capability | Location |
|---|---|
| SEO E-commerce Agent | `agents/seo-ecommerce-agent.md` |
| E-commerce skills (product audit, Product/Offer/ProductGroup schema, merchant-data consistency, marketplace intelligence, keyword gap, faceted-nav governance, agentic-commerce readiness) | `skills/ecommerce-seo-skills.md` |
| Programmatic SEO governance | `skills/programmatic-seo-governance.md` |
| Geo-grid local rank, GBP audit, competitor radius, NAP verification | `skills/geo-grid-local-rank-skills.md` |
| Competitor comparison / alternatives page build | `skills/competitor-comparison-pages.md` |
| Rendered visual audit + single-page audit | `skills/rendered-visual-audit-and-page-entry.md` |
| Knowledge registry (8 files) | `knowledge/schema-deprecation-registry.md`, `knowledge/google-algorithm-updates.json`, `knowledge/geo-readiness-rubric.md`, `knowledge/eeat-quality-rubric.md`, `knowledge/core-web-vitals-gates.md`, `knowledge/free-backlink-sources.md`, `knowledge/ai-image-labeling.md`, `knowledge/parasite-seo-expired-domain-checks.md` |
| Live PageSpeed/CrUX adapter (SSRF-safe) and SQLite evidence/drift store | `adapters/google_pagespeed_live.py`, `adapters/evidence_store.py` |
| E-commerce report template | `templates/ecommerce-seo-report.md` |
| Single-page audit workflow | `workflows/single-page-audit-workflow.md` |
| Architecture references (MCP mapping, evidence cache, plugin packaging) | `docs/mcp-server-mapping.md`, `docs/evidence-cache-contract.md`, `docs/plugin-packaging.md`, `docs/plugin.example.json` |

## How it is wired

- The SEO E-commerce Agent is registered in `runtime/executor.py` (`AGENT_FILE_NAMES`) and `runtime/routing.py` (route + support map), and listed in `agents/AGENT_INDEX.md`, `README.md`, and `SYSTEM_MAP.md`. Because the per-LLM control files read from these indexes, the agent is available to every runtime (Codex, ChatGPT, Claude, Claude Code, Replit, Manus) without per-file edits.
- Every new skill is listed in `skills/SKILL_INDEX.md` with a matching entry in `skills/deep-skill-procedures.md` (the semantic test suite enforces that pairing).
- `google_pagespeed_live` is registered in `adapters/registry.py` as `google_pagespeed_live` and `pagespeed_live`. `evidence_store` is intentionally not a registered fetch-adapter; the `seo-drift-monitor` skill and adapters write normalized snapshots to it. See `docs/evidence-cache-contract.md`.
- The knowledge registry is listed in `knowledge/knowledge-sources.md`. Time-sensitive entries are evidence-labeled; re-verify against the primary sources before client-facing use.

## Validation

Green locally and in CI (`.github/workflows/validate.yml`): repository validator, schema-example validation, and the full pytest suite. Run locally with `scripts/validate-repository.ps1`, `python scripts/validate_schema_examples.py`, and `pytest -q`.

## Accuracy note

The knowledge files keep the system's evidence hierarchy: facts are labeled and time-sensitive claims are marked for re-verification. `knowledge/google-algorithm-updates.json` was independently re-verified against Google-owned sources on 2026-07-10 and is current through the June 24-26 2026 spam update.
