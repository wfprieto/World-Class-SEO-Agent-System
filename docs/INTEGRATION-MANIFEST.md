# Integration Record

**Status:** Merged into `main` (Batch 2 released; squash commit 0612201)  
**Version:** 1.6.0  
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

## Batch 2 (v1.6.0) - merged into `main`

| Capability | Disposition | Where it lives |
|---|---|---|
| FLOW prompt library | Integrated as written | `skills/seo-flow-skill.md` (skill `flow-prompt-run`); stage files in `skills/flow-prompts/` are references, not separate skills |
| Rendered-page adapter | Integrated with narrow changes | `adapters/rendered_page.py`, registered as `rendered_page`; returns `AdapterResult`; Playwright optional |
| SERP-overlap clustering | Integrated as written | `scripts/serp_cluster.py` + `skills/seo-cluster-skill.md` (skill `serp-overlap-cluster`) |
| Report generator | Integrated with narrow changes | `scripts/seo_pdf_report.py`, consumes the canonical agent-output shape; HTML fallback when WeasyPrint is absent |
| MCP extension registry | Integrated with narrow changes | `adapters/mcp_extensions.py` is the machine-readable source; `docs/mcp-server-mapping.md` defers to it |
| Drift monitoring | **Rejected as a separate system; merged** | `adapters/page_drift.py` layers page-state drift on the existing evidence store (`metric_group = "page_state"`). The proposed standalone `drift_store.py` SQLite database was not added, because a second database would create a competing source of truth |

One SSRF policy: `adapters/url_safety.py` is the single canonical outbound URL validator.
`adapters/google_pagespeed_live.py` delegates to it, so the kit no longer carries two
implementations. `.seo-cache/` and `*.db` are git-ignored; the evidence database is never committed.

Optional dependencies (none required): `playwright` for live rendering, `weasyprint` and
`matplotlib` for PDF output. Absent any of them, the kit still runs credential-free and the
adapters report the missing evidence honestly rather than claiming it. Both optional paths are
dependency-injected (`render_fn`, `pdf_renderer`), so the success branches are tested without a live
browser or a native PDF runtime; `ReportResult.pdf_verified` is true only when a real PDF file exists.

Evidence integrity: the canonical store is tamper-evident. `EvidenceStore._migrate_schema()` backfills
digests only for legacy rows that lack them and never rewrites a row that already carries both digests, so
tampered payloads and altered protected metadata are detected on read and by `integrity_check()`. Deliberate
digest rewriting lives in the separate `EvidenceStore.repair_digests(confirm=True)`, which is never invoked
during initialization. `adapters/page_drift.verify_untampered()` is retained as defence in depth: it checks
stored digests on a raw connection before the store opens, so a drift verdict is never produced from evidence
that cannot be trusted.

Generated artifacts (reports, cluster maps) default to `outputs/`, which is git-ignored, so they cannot
enter source control.

## Accuracy note

The knowledge files keep the system's evidence hierarchy: facts are labeled and time-sensitive claims are marked for re-verification. `knowledge/google-algorithm-updates.json` was independently re-verified against Google-owned sources on 2026-07-10 and is current through the June 24-26 2026 spam update.
