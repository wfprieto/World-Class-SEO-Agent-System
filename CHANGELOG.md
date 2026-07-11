# Changelog

All notable changes to this repository will be documented in this file.

This project follows semantic versioning where possible:

- MAJOR: breaking changes to agent contracts, schemas, or operating workflows.
- MINOR: new agents, skills, workflows, templates, or knowledge sources.
- PATCH: clarifications, documentation fixes, and non-breaking improvements.

## [1.7.0] - 2026-07-11

### Added

- `skills/local-execution-skills.md`: one governed Desktop Commander execution skill (`desktop-commander-execution`) with allowed / approval-gated / prohibited permission tiers, evidence recording, and tool-overlap resolution. Individual tool functions are not registered as skills.
- `knowledge/seo-vertical-profiles.md` and `scripts/vertical_profiles.py`: the six vertical architecture profiles (generic, ecommerce, local-service, saas, publisher, agency). Low-confidence detection never silently routes; two or more strongly evidenced models produce a declared HYBRID route. The detection authority remains `docs/plugin-packaging.md` section 9 and `runtime/routing.py` remains the only router.
- `knowledge/agent-friendly-pages.md`: evidence-labeled page-construction reference. Records that llms.txt is not required for Google Search, that crawler access does not guarantee citation, and that Google-Extended is a robots.txt token only rather than a log user-agent. Cross-references `knowledge/geo-readiness-rubric.md` and the rendered-visual-audit skill instead of duplicating them.
- `knowledge/dma-consent-mode-v2.md`, `scripts/consent_mode_diagnostic.py`, and the `consent-mode-diagnostic` skill: Consent Mode v2 signals, command ordering, region precedence, Basic versus Advanced behavior, and unknown/stale handling. It never grants consent, never bypasses a CMP, never exposes consent strings or identifiers, and never claims legal compliance.
- `scripts/content_brief_evidence.py`: website-relevance gate and evidence-based SERP competitor assessment.
- `tests/test_batch3_tactical.py`.

### Changed

- `skills/content-ia-skills.md`: the canonical `content-brief` skill now requires a website-relevance verdict (RELEVANT, CONDITIONALLY_RELEVANT, NOT_RELEVANT, INSUFFICIENT_EVIDENCE) and an evidence-based SERP competitor assessment before any outline work. Search volume never green-lights an unrelated topic, and a brief requires a stated information gain. Comparison weights are labeled configurable kit heuristics, not Google scores or ranking factors. No competing content-brief-v2 skill was created.
- `docs/INTEGRATION-MANIFEST.md`: corrected source-of-truth drift. It described Batch 2 as "staged, not released" and carried version 1.5.0 after Batch 2 had already been merged (squash commit 0612201). Reconciled to the real repository state.

## [1.6.0] - 2026-07-10

### Added

- `adapters/url_safety.py`: single canonical outbound URL-safety policy (SSRF, credentials, ports, non-global addresses).
- `adapters/rendered_page.py`: optional Playwright render adapter returning `AdapterResult`, with SPA detection, subresource guarding, accessibility-tree capture, and truthful raw-fetch fallback.
- `adapters/page_drift.py`: page-state drift over the existing evidence store (`metric_group = "page_state"`), with SHA-256 fingerprints and severity classification.
- `adapters/mcp_extensions.py`: declarative MCP extension registry with cost tier, allowed and forbidden operations, credential presence detection, and no provider calls.
- `scripts/serp_cluster.py` and `skills/seo-cluster-skill.md`: deterministic SERP-overlap topic clustering (`serp-overlap-cluster`).
- `scripts/seo_pdf_report.py`: branded A4 report from the canonical agent-output shape, with a styled HTML fallback.
- `skills/seo-flow-skill.md` and `skills/flow-prompts/`: clean-room FLOW stage prompt library (`flow-prompt-run`).
- `tests/test_batch2_integration.py` and `tests/test_batch2_hardening.py`: SSRF, optional-dependency
  success paths via injection, SPA, BOM, deterministic clustering, concurrent and tampered evidence,
  adversarial MCP governance, reporting-contract resilience, index integrity, and the rollback boundary.
- `adapters/mcp_extensions.validate_registry()`: fails closed on tool-name shadowing, silent capability
  expansion, destructive operations, missing cost gates, malformed credentials, description poisoning,
  and unguarded SSRF-capable providers.
- `adapters/page_drift.verify_untampered()`: verifies stored payload digests on a raw connection before
  the evidence store opens, so a drift verdict is never produced from tampered evidence.
- `scripts/seo_pdf_report.ReportResult`: states truthfully whether a PDF or the HTML fallback was produced.

### Changed

- `adapters/google_pagespeed_live.py` now delegates URL validation to `adapters/url_safety.py`, so the kit has one SSRF implementation instead of two. Behavior is unchanged.
- `adapters/registry.py` registers `rendered_page`.
- `docs/mcp-server-mapping.md` now defers to `adapters/mcp_extensions.py` as the machine-readable source.
- `docs/evidence-cache-contract.md` records that page drift is a metric group in the one evidence store, not a second database.
- `.gitignore` excludes `.seo-cache/` and `*.db` so the evidence database is never committed.

### Fixed

- **Evidence tamper-evidence restored.** `EvidenceStore._migrate_schema()` previously recomputed and
  overwrote `payload_sha256` and `record_sha256` for every row on each open, so an externally tampered
  payload or altered protected metadata was silently re-blessed and `integrity_check()` could never detect
  it. Migration now backfills digests only for legacy rows that genuinely lack them, never rewrites a row
  that already carries both digests, and raises `EvidenceIntegrityError` on a partial-digest mismatch
  instead of repairing it. Reopening an untampered database preserves its hashes and is idempotent.
- Deliberate digest rewriting moved to a separate, explicitly invoked `EvidenceStore.repair_digests(confirm=True)`.
  It is never called during initialization and refuses to run without explicit confirmation, because rewriting a
  digest over tampered content destroys tamper-evidence.

### Rejected

- The proposed standalone `drift_store.py` SQLite database. The canonical evidence store already provides SHA-256 digests and drift comparison; a second database would create a competing source of truth.

## [1.5.0] - 2026-07-10

### Added

- SEO E-commerce Agent plus e-commerce skills (product-page audit, Product/Offer/ProductGroup schema validation, marketplace intelligence, marketplace keyword gap, faceted-navigation governance, agent-commerce readiness).
- Programmatic SEO governance skill with doorway and index-bloat gates.
- Geo-grid local rank, GBP profile audit, competitor radius map, and cross-platform NAP verification skills.
- Competitor comparison and alternatives page build skill.
- Rendered visual audit skill and single-page audit entry point with `workflows/single-page-audit-workflow.md`.
- Knowledge registry: schema-deprecation registry, machine-readable Google algorithm-update history, GEO readiness rubric, E-E-A-T rubric, Core Web Vitals gates, free backlink sources, AI-image labeling, and parasite/expired-domain checks.
- Live key-only PageSpeed/CrUX adapter with SSRF-safe validation and a persistent SQLite evidence/drift store.
- Deep procedures for every new skill, `templates/ecommerce-seo-report.md`, and `docs/` architecture references (MCP mapping, evidence-cache contract, plugin packaging).

### Changed

- Registered the SEO E-commerce Agent in the executor and router, and the PageSpeed live adapter in the registry.
- Updated AGENT_INDEX, SKILL_INDEX, README, SYSTEM_MAP, and request routing to reference the new capabilities.

## [1.4.2] - 2026-07-03

### Added

- Registry aliases for backlink, CrUX, GA4, GSC, PageSpeed and rank tracking adapters.
- Runtime handoff emission when escalation is triggered.
- Schema-aligned runtime `agent_output` payloads.
- Deep procedures for accessibility audit, analytics synthesis, conversion intent, landing page CRO, local landing page briefs and regional keyword maps.
- Additional anonymized GSC and Core Web Vitals export examples.
- Tenacity retry/backoff and logging for live LLM clients.

### Changed

- Removed backticks from diagnostic budget/page-size values to prevent false skill-reference positives.
- AI Principal SEO Scientist now explicitly references `workflows/continuous-learning-workflow.md`.

## [1.4.1] - 2026-07-03

### Added

- `SYSTEM_MAP.md` as a fast navigation map for humans and LLMs.
- Semantic tests that verify system map presence, executor coverage, router workflow paths and router agent file coverage.

### Changed

- Expanded runtime routing to cover specialist agents beyond the common audit/content/technical paths.
- Added `.pytest_cache/` to `.gitignore`.
- Updated README start path to point first to the system map.

## [1.4.0] - 2026-07-03

### Added

- Adapter implementation guide in `adapters/README.md`.
- Categorized SEO tool connection catalog in `adapters/TOOLS.md`.
- Google Search Console live OAuth2 adapter example.
- Adapter stubs for CrUX, hreflang validation, sitemap validation, accessibility checks, GBP/local data, redirect chains, AI citation monitoring, knowledge graph checks and robots.txt validation.
- Schema validation examples for handoff payloads, decision records and rule updates.
- Anonymized/sanitized real-site GSC export pattern.
- Expanded adapter tests covering existing parsers, new stubs, registry coverage and missing-secret behavior for live GSC.

### Changed

- Schema example validation now checks agent outputs plus handoff, decision and rule-update examples.
- Runtime adapter registry now exposes the expanded adapter set.

## [1.3.0] - 2026-07-03

### Added

- Model-agnostic runtime execution with async LLM clients, streaming hooks, memory and tool dispatch.
- Offline echo LLM client for deterministic tests and dry runs.
- Optional OpenAI-compatible and Anthropic-compatible clients configured through environment variables.
- Runtime tests for LLM execution and adapter dispatch.
- Repository semantic test requiring every indexed skill to have a deep procedure.

### Changed

- CLI can now route only or execute routed workflows with `--execute`.
- Runtime documentation now includes dry-run, live LLM and tool-dispatch examples.

## [1.2.1] - 2026-07-03

### Added

- Anti-AI public-facing writing skill for visitor-visible website and app copy.
- Public-facing writing standard requiring the skill for headings, metadata, body copy, buttons, forms, alt text, captions, transcripts, onboarding text and error messages.

### Changed

- SEO Copywriter/Content Agent now requires `anti-ai-public-writing` before visitor-facing text is published.

## [1.2.0] - 2026-07-03

### Added

- Lightweight Python runtime with request routing, session state, and orchestrator facade.
- Tool adapter contracts and offline-safe parsers for GSC exports, GA4 exports, crawler CSVs, server logs, PageSpeed/Lighthouse payloads, schema validation, rank tracking, and backlink data.
- Semantic schema validation for every example `agent-output.json`.
- Pytest semantic test suite covering schemas, runtime routing, adapters, repository contracts, and a mock end-to-end flow.
- Deep tool-aware procedures for the original grouped skills.
- Anonymized production-style example with crawl, search performance, analytics-style inputs, and conforming agent output.

### Changed

- Expanded GitHub Actions validation to install Python dependencies, run schema conformance checks, and execute the semantic test suite.
- Updated system documentation to distinguish documentation contracts, executable runtime, and adapter responsibilities.

## [1.1.0] - 2026-07-03

### Added

- SEO Output Report Agent for plain-language stakeholder reporting.
- Plain-language SEO report skill, template, and worked example.
- SEO Diagnostic Infrastructure Agent for budget-aware SEO tool stack, audit reporting, grading, dashboard, and monitoring setup.
- Diagnostic stack design skill, template, and worked example.
- Website/app platform and code-access intake for diagnostic stack recommendations.
- Missing agent-referenced templates.
- Complete definitions for additional referenced skills.
- Skill definition standard and execution playbooks.
- Handoff payload schema.
- Session state schema.
- Monitoring workflow.
- Orchestration guide.
- Regional search engine knowledge source.
- Repository validation script and GitHub Actions workflow.
- Security policy and code of conduct.
- System prompts for original grouped skill definitions.
- Mermaid decision trees for continuous learning and system improvement workflows.

### Changed

- Strengthened `agent-output.schema.json` to match the system output contract.
- Added stricter schema descriptions, examples, and `additionalProperties: false`.
- Expanded workflow decision trees and failure handling.
- Added AI content disclosure and INP-specific quality gates.
- Added `follow_up` to the standard agent output schema.
- Added descriptions and examples to the session state schema.

## [1.0.0] - 2026-07-03

### Added

- Initial World-Class SEO Agent System.
- 22 specialist SEO agents.
- Model-specific control files.
- Core skill catalogue.
- Workflows, quality gates, anti-patterns, schemas, and templates.
