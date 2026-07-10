# Integration Manifest: SEO Kit Improvement Set

**Status:** Controlled integration candidate  
**Manifest version:** 2.0.0  
**Last reviewed:** 2026-07-10  
**Scope:** These 22 files only

## Purpose

This manifest is the source of truth for placement, dependencies, wiring, and release gates for the SEO kit improvement set. It does not override stricter host-repository governance, security, privacy, legal, routing, or evidence rules.

A file is not runtime-ready merely because it parses, compiles, or reads well. Runtime readiness requires successful placement, reference resolution, registration, integration tests, failure-path tests, and owner approval in the host repository.

## Authority and conflict handling

Resolve conflicts in this order:

1. Applicable law, platform policy, and current primary-source documentation.
2. Host-repository security, privacy, approval, evidence, and release controls.
3. Host schemas, indexes, routing rules, and canonical contracts.
4. This manifest.
5. Agent and skill files in this set.
6. Knowledge and implementation-reference files in this set.
7. Packaging examples.

When two rules conflict, stop the affected integration, record the conflict, and escalate to the repository owner. Do not silently choose a weaker rule.

## Integration states

| State | Meaning |
|---|---|
| `SOURCE_ONLY` | File exists but has not been placed, registered, or tested in the host. |
| `DROP_IN_CANDIDATE` | Placement may be direct after collision and reference checks. |
| `WIRING_REQUIRED` | Host code, routing, registry, index, or build changes are required. |
| `VERIFY_AT_RUN` | Time-sensitive provider, policy, pricing, or platform behavior must be rechecked. |
| `RUNTIME_READY` | Host wiring and required automated and smoke tests passed. |
| `BLOCKED` | A missing dependency, conflict, failed gate, or unapproved risk prevents integration. |

## Canonical inventory

| File | Canonical target | Primary consumers | Initial state | Required integration action |
|---|---|---|---|---|
| `INTEGRATION-MANIFEST.md` | `docs/integration/SEO-KIT-MANIFEST.md` | Maintainers, release reviewers | `DROP_IN_CANDIDATE` | Reconcile actual host paths and update states after integration. |
| `OWNERSHIP-AND-LICENSE-NOTE.md` | `docs/legal/SEO-KIT-PROVENANCE.md` | Owner, legal reviewer | `VERIFY_AT_RUN` | Complete provenance ledger and select an outbound license before distribution. |
| `plugin-packaging.md` | `docs/plugin-packaging.md` | Release engineering | `WIRING_REQUIRED` | Build a self-contained Claude Code plugin tree from source. |
| `plugin.example.json` | `.claude-plugin/plugin.json` in the built plugin | Claude Code loader | `WIRING_REQUIRED` | Add only verified component paths and validate with the current CLI. |
| `mcp-server-mapping.md` | `docs/mcp-server-mapping.md` | Runtime integrators, operators | `VERIFY_AT_RUN` | Confirm connected tools, permissions, pricing, and retention at execution time. |
| `evidence-cache-contract.md` | `docs/evidence-cache-contract.md` | Adapters, drift monitor | `WIRING_REQUIRED` | Reconcile cache and evidence-store behavior with host policy. |
| `evidence_store.py` | `adapters/evidence_store.py` | Adapters, drift monitor | `WIRING_REQUIRED` | Add to runtime, run migration/concurrency/integrity tests, and define retention ownership. |
| `google_pagespeed_live.py` | `adapters/google_pagespeed_live.py` | CWV workflows, adapter registry | `WIRING_REQUIRED` | Register against the host `AdapterResult` contract and run opt-in live credential tests. |
| `rendered-visual-audit-and-page-entry.md` | `skills/rendered-visual-audit-and-page-entry.md` | Router, technical and accessibility agents | `WIRING_REQUIRED` | Split into plugin skills if packaged; register route precedence and evidence reuse. |
| `seo-ecommerce-agent.md` | `agents/seo-ecommerce-agent.md` | Agent router, e-commerce skills | `WIRING_REQUIRED` | Add required host frontmatter and register without name collisions. |
| `ecommerce-seo-skills.md` | `skills/ecommerce-seo-skills.md` | E-commerce agent, router | `WIRING_REQUIRED` | Register seven named skills; split into one `SKILL.md` per skill for plugin output. |
| `geo-grid-local-rank-skills.md` | `skills/geo-grid-local-rank-skills.md` | Local SEO agent | `WIRING_REQUIRED` | Register four named skills and preserve tier, cost, privacy, and identity controls. |
| `competitor-comparison-pages.md` | `skills/competitor-comparison-pages.md` | Content agent, strategist | `WIRING_REQUIRED` | Register BUILD, AUDIT, and REFRESH modes with claim and legal review gates. |
| `programmatic-seo-governance.md` | `skills/programmatic-seo-governance.md` | Technical agent, SEO ScrumMaster | `WIRING_REQUIRED` | Register the governance skill and connect launch, monitoring, and rollback decisions. |
| `schema-deprecation-registry.md` | `knowledge/schema-deprecation-registry.md` | Schema and e-commerce skills | `VERIFY_AT_RUN` | Make feature-state lookup mandatory before schema generation. |
| `google-algorithm-updates.json` | `knowledge/google-algorithm-updates.json` | Drift and analytics workflows | `VERIFY_AT_RUN` | Validate dates and official sources before client-facing correlation work. |
| `core-web-vitals-gates.md` | `knowledge/core-web-vitals-gates.md` | CWV triage | `DROP_IN_CANDIDATE` | Map states and numeric units to the host report model. |
| `eeat-quality-rubric.md` | `knowledge/eeat-quality-rubric.md` | Content audit | `DROP_IN_CANDIDATE` | Preserve its diagnostic, non-ranking-factor framing. |
| `geo-readiness-rubric.md` | `knowledge/geo-readiness-rubric.md` | GEO/AIO audit | `VERIFY_AT_RUN` | Recheck crawler controls and platform-specific capabilities at execution time. |
| `free-backlink-sources.md` | `knowledge/free-backlink-sources.md` | Off-page workflows | `VERIFY_AT_RUN` | Confirm provider access, quotas, terms, and metric definitions before use. |
| `ai-image-labeling.md` | `knowledge/ai-image-labeling.md` | Image and e-commerce work | `VERIFY_AT_RUN` | Validate final delivered assets and current Merchant Center requirements. |
| `parasite-seo-expired-domain-checks.md` | `knowledge/parasite-seo-expired-domain-checks.md` | Security and strategy agents | `VERIFY_AT_RUN` | Recheck current spam-policy wording before client recommendations. |

## Canonical skill inventory

| Source file | Skill IDs |
|---|---|
| `rendered-visual-audit-and-page-entry.md` | `rendered-visual-audit`, `single-page-audit` |
| `ecommerce-seo-skills.md` | `product-page-seo-audit`, `product-schema-validate-generate`, `merchant-data-consistency-audit`, `marketplace-intelligence`, `marketplace-keyword-gap`, `faceted-navigation-governance`, `agentic-commerce-readiness-check` |
| `geo-grid-local-rank-skills.md` | `geo-grid-rank-scan`, `gbp-profile-audit`, `competitor-radius-map`, `cross-platform-nap-verify` |
| `competitor-comparison-pages.md` | `competitor-comparison-page-build` |
| `programmatic-seo-governance.md` | `programmatic-seo-governance` |

A skill rename or alias requires an index, router, plugin-build, documentation, and regression-test update. Do not silently preserve two active names for the same skill.

## Canonical path rules

- All documented paths are repository-root-relative, case-sensitive, and use `/` separators.
- A source file has one approved destination. Compatibility aliases must be documented and tested.
- Generated plugin artifacts must never overwrite canonical source files.
- Plugin paths must remain inside the plugin root. Reject absolute paths, `..` escapes, and unresolved symlinks.
- Path or filename changes require a full reference scan and migration note.

## Required host dependencies

Confirm these or their documented equivalents before declaring runtime readiness:

- agent and skill indexes;
- the host skill-definition standard;
- adapter base classes and registry;
- router and request-routing rules;
- report schemas and templates;
- technical, schema, content, CWV, local, and GEO skills referenced by orchestration;
- security, privacy, cost-approval, and legal-escalation mechanisms.

A missing or incompatible dependency blocks only the affected capability, but the omission must be explicit.

## Dependency order

Integrate in this order:

1. Ownership, provenance, and host-governance reconciliation.
2. Knowledge files and current-source checks.
3. Evidence cache and persistent evidence store.
4. Live adapters and provider mappings.
5. Rendering and single-page routing.
6. Specialist agent and skills.
7. Plugin build and packaging.
8. End-to-end regression, smoke, security, cost, and rollback tests.

## Required wiring

### Evidence subsystem

- Use one canonical normalized result shape.
- Write only approved normalized data to the evidence store.
- Preserve source, scope, capture time, schema version, and result status.
- Never persist secrets or unnecessary personal data.
- Compare only compatible metric and schema versions.

### PageSpeed and CrUX adapter

- Register under one unique key.
- Missing credentials must produce the host-standard nonfatal configuration state.
- Preserve the distinction between Lighthouse lab evidence and CrUX field evidence.
- Treat CrUX no-data responses as unavailable evidence, not a performance failure.
- Never expose API keys in logs, warnings, stored URLs, or reports.

### Single-page routing

- Explicit user focus overrides automatic classification.
- A single-URL audit must not silently expand into a full-site audit.
- Missing skills create named omissions and reduced coverage.
- Metered calls require approval and a ceiling before execution.
- The router synthesizes and deduplicates findings; specialist logic remains in specialist skills.

### Specialist routing

- E-commerce signals route to the e-commerce agent and relevant skills.
- Local/maps work distinguishes public presence from measured rank.
- Comparison-page work requires claim-level substantiation and disclosure.
- Programmatic work requires launch, monitoring, and rollback governance.
- Low-confidence or mixed business-type detection is advisory and user-overridable.

## Release gates

Release is blocked when any of the following is true:

- a referenced file, skill, agent, route, or adapter cannot be resolved;
- a time-sensitive claim is used without a current primary-source check;
- a metered provider can run without explicit approval and a hard ceiling;
- secrets, client-confidential evidence, cache databases, or screenshots can be committed by default;
- structured data describes hidden, fabricated, or materially different content;
- a report treats unavailable evidence as a pass;
- source-only analysis is represented as rendered or live-data completion;
- plugin files reference paths outside the plugin root;
- JSON parsing, Python compilation, schema, routing, or smoke tests fail;
- provenance or license status is unresolved for the intended distribution;
- rollback is undefined for a high-impact change.

## Minimum validation suite

Run and retain evidence for:

1. Exact inventory and duplicate-name scan.
2. Internal-reference and canonical-path scan.
3. JSON parsing and date/source validation.
4. Python compilation, unit tests, and negative-path tests.
5. Evidence-store migration, integrity, retention, deletion, and concurrent-write tests.
6. Adapter credential, timeout, retry, redirect, response-size, parsing, and redaction tests.
7. Router precedence, classification, missing-skill, deduplication, coverage, and cost-gate tests.
8. Structured-data visible-content and current-feature checks.
9. Plugin validation with `claude plugin validate <plugin-root> --strict` on a supported Claude Code release.
10. A smoke test for every published entry point and a documented rollback test.

Every validation claim must identify the artifact tested, method or command, date, result, and reviewer.

## Failure and escalation

| Condition | Required response |
|---|---|
| Missing dependency | Mark the affected capability `BLOCKED` or `PARTIAL`; continue only with independent checks. |
| Naming or path collision | Stop the conflicting integration and open a decision record. |
| Primary source unavailable | Keep the claim unknown or remove it from executable and client-facing use. |
| Metered cost unknown or over ceiling | Do not call the provider; use an approved fallback. |
| Security, privacy, or legal gate fails | Stop the affected work and escalate before further execution. |
| Partial provider or runtime result | Preserve valid evidence, identify omissions, and reduce coverage and confidence. |
| Critical test fails | Do not release; fix or obtain an explicit documented exception from the accountable owner. |

Critical exceptions must state the evidence, alternatives, risk, approver, scope, expiration date, and rollback plan.

## Completion report

A final integration report must include:

- exact host commit or release tested;
- installed file map and hashes;
- registered agents, skills, routes, adapters, and provider capabilities;
- automated and manual test results;
- active limitations and skipped checks;
- approved cost, privacy, security, and legal exceptions;
- rollback instructions;
- final state for every file in this inventory.
