# Changelog

All notable changes to this repository will be documented in this file.

This project follows semantic versioning where possible:

- MAJOR: breaking changes to agent contracts, schemas, or operating workflows.
- MINOR: new agents, skills, workflows, templates, or knowledge sources.
- PATCH: clarifications, documentation fixes, and non-breaking improvements.

## [1.1.0] - 2026-07-03

### Added

- SEO Output Report Agent for plain-language stakeholder reporting.
- Plain-language SEO report skill, template, and worked example.
- SEO Diagnostic Infrastructure Agent for budget-aware SEO tool stack, audit reporting, grading, dashboard, and monitoring setup.
- Diagnostic stack design skill, template, and worked example.
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
