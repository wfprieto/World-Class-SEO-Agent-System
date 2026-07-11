# Integration Record

**Status:** Integrated into `main` through Batch 3 (squash commit `cf782d9`)  
**Version:** 1.7.0  
**Last reviewed:** 2026-07-11

This file records capabilities already integrated into the canonical `main` branch. It does not claim that a Git tag, marketplace publication, package distribution, deployment, or live provider validation exists. See `CHANGELOG.md` for the running history and Unreleased work.

## Integrated capability map

| Capability | Canonical location |
|---|---|
| Agent roster and ownership | `agents/AGENT_INDEX.md`, `agents/` |
| Skill index and execution entries | `skills/SKILL_INDEX.md`, `skills/deep-skill-procedures.md` |
| E-commerce SEO | `agents/seo-ecommerce-agent.md`, `skills/ecommerce-seo-skills.md` |
| Programmatic SEO governance | `skills/programmatic-seo-governance.md` |
| Local maps and identity skills | `skills/geo-grid-local-rank-skills.md` |
| Competitor comparison governance | `skills/competitor-comparison-pages.md` |
| Rendered visual and single-page audit | `skills/rendered-visual-audit-and-page-entry.md` |
| Agent-friendly pages | `knowledge/agent-friendly-pages.md` |
| Six vertical architecture profiles | `knowledge/seo-vertical-profiles.md`, `scripts/vertical_profiles.py` |
| Content-brief relevance and SERP evidence | `skills/content-ia-skills.md`, `scripts/content_brief_evidence.py` |
| Consent Mode v2 diagnostic | `knowledge/dma-consent-mode-v2.md`, `scripts/consent_mode_diagnostic.py` |
| Page rendering and drift | `adapters/rendered_page.py`, `adapters/page_drift.py` |
| Live PageSpeed and CrUX | `adapters/google_pagespeed_live.py` |
| Canonical evidence store | `adapters/evidence_store.py` |
| MCP capability registry | `adapters/mcp_extensions.py` |
| Report generation | `scripts/seo_pdf_report.py` |
| SERP-overlap clustering | `scripts/serp_cluster.py`, `skills/seo-cluster-skill.md` |
| FLOW prompt library | `skills/seo-flow-skill.md`, `skills/flow-prompts/` |

## Wiring rules

- `runtime/routing.py` is the canonical request router.
- `runtime/executor.py` is the canonical agent-file name registry used by executable routing.
- Every indexed skill retains one exact `## <skill-id>` entry in `skills/deep-skill-procedures.md`.
- Detailed specialist rules live in their canonical skill files; the deep-procedure catalog must not become a competing rulebook.
- `adapters/url_safety.py` is the single outbound URL-safety policy.
- `adapters/evidence_store.py` is the single durable SEO evidence store. Runtime event memory is separate and must not replace it.
- `adapters/mcp_extensions.py` is the machine-readable optional-provider capability registry.
- Generated reports, databases, caches, screenshots, credentials, and client artifacts remain outside source control.

## Batch 2, v1.6.0

Batch 2 integrated the FLOW prompt library, rendered-page adapter, SERP-overlap clustering, canonical report generator, MCP extension registry, and page-state drift over the existing evidence store. The proposed second drift database was rejected. URL validation was consolidated in `adapters/url_safety.py`.

Optional Playwright, WeasyPrint, and matplotlib paths degrade truthfully when dependencies are missing. Their injected success branches are tested, but native live execution remains a separate verification state.

## Batch 3, v1.7.0

Batch 3 integrated:

- governed Desktop Commander execution boundaries;
- website-relevance and observed-SERP gates for content briefs;
- generic, e-commerce, local-service, SaaS, publisher, and agency architecture profiles;
- agent-friendly page-construction guidance;
- a fixture-only Consent Mode v2 diagnostic;
- source-of-truth correction and hardening tests.

The Batch 3 merge is `cf782d9881258366aae7f9b94c1267be6717e94a`. The documented human waiver preserves the actual artifact review counts and does not represent any artifact as 20/20.

## Validation

Canonical validation on `main` includes:

```powershell
./scripts/validate-repository.ps1
python scripts/validate_schema_examples.py
pytest -q
```

GitHub Actions runs the same repository contracts on pull requests and pushes to `main`.

## Evidence and release states

These states are distinct:

- **Integrated into main:** code exists in the canonical branch.
- **Released or tagged:** a reviewed semantic release or Git tag exists.
- **Published or distributed:** a package, plugin, or marketplace artifact is available.
- **Deployed:** a running environment uses the release.

This record currently attests only to integration into `main` through v1.7.0.
