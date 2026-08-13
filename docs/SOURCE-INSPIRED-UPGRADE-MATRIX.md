# Source-Inspired Upgrade Matrix

## Purpose

This matrix governs how external SEO repositories may inform upgrades to this system.
It prevents blind copying, orphan files, duplicated rules, and unverified claims.

Canonical machine-readable file:

`evaluation/upgrade-source-matrix.json`

## APIVR Tier

Comprehensive.

The upgrade touches agents, skills, knowledge, workflows, adapters, examples, tests, and
release confidence. Each phase must be audited, implemented, verified, and re-baselined
before the next phase becomes the active work unit.

## Source Policy

Allowed:

- Extract generalized SEO procedures.
- Extract test-fixture categories and expected-finding ideas.
- Extract adapter and MCP contract patterns.
- Extract source-backed reference topics.
- Rewrite all target artifacts in this repository's architecture, vocabulary, and quality gates.

Forbidden:

- Copy external repository prose verbatim into target artifacts.
- Copy external source code into runtime modules.
- Retain external repository branding as system identity.
- Create orphan imports or import files that are not connected to agents, skills, workflows, tests, or registries.
- Add paid-tool recommendations without budget, credential, and access guardrails.

## Inventoried Sources

| Source | Observed HEAD | Primary value |
|---|---:|---|
| `AgriciDaniel/claude-seo` | `6cf1ea9` | SEO knowledge, FLOW prompt packs, reference packs, specialist procedures |
| `every-app/open-seo` | `61c0b0c` | MCP tools, DataForSEO shaping, GSC, AI search, rank tracking, audit workflows, bad SEO fixtures |
| `stefankirkegaard/open-seo-github` | `82d6363` | Lean OpenSEO implementation patterns and self-hosting/product decisions |
| `TahaHachana/OpenSEO` | `670fd11` | Historical page-review checklist concepts |

## Upgrade Phases

| Phase | Unit | Outcome |
|---:|---|---|
| 1 | Source extraction governance | Verified matrix, source policy, validator, and tests |
| 2 | FLOW expansion | Verified Find, Leverage, Optimize, Win, and Local operating prompts |
| 3 | Knowledge reference expansion | Verified source-postured reference packs connected to agents and skills |
| 4 | Bad SEO fixtures | Verified reproducible fixture pack with expected findings |
| 5 | Adapter/tooling upgrade | Verified cost-aware adapter and tool routing policy |
| 6 | Final cross-reference audit | Verified no-orphan cross-reference tests and APIVR closeout |

## Phase Gates

Each phase must pass:

- Its unit-specific verification commands in `evaluation/upgrade-source-matrix.json`.
- Repository semantic checks for touched surfaces.
- APIVR Phase 4 implementation audit.
- APIVR Phase 5 verification report.
- A 20-pass summary that counts only concrete improvements.

## Current Status

Phase 1 is verified. Phase 2 is verified. Phase 3 is verified. Phase 4 is verified.
Phase 5 is verified. Phase 6 is verified.
