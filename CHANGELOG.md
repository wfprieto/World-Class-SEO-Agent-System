# Changelog

All notable changes to this repository will be documented in this file.

This project follows semantic versioning where possible:

- MAJOR: breaking changes to agent contracts, schemas, or operating workflows.
- MINOR: new agents, skills, workflows, templates, or knowledge sources.
- PATCH: clarifications, documentation fixes, and non-breaking improvements.

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
