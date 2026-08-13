# LibHunt Source Ingestion Plan

## Purpose

This plan governs clean-room upgrades inspired by LibHunt and LibHunt-adjacent SEO repositories.
It keeps external sources useful without letting them become copied prose, copied code, unverified
rules, or orphan files.

Canonical machine-readable file:

`evaluation/libhunt-source-ingestion-matrix.json`

## APIVR Tier

Comprehensive.

The upgrade touches canonical knowledge, product-proof rules, fixtures, skills, adapters, runtime
guardrails, docs, and tests. Each phase must be implemented, audited, verified, and re-baselined
before the next phase begins.

## Source Policy

Allowed:

- Extract generalized SEO heuristics.
- Extract deterministic rule categories.
- Extract adapter-hardening edge cases.
- Extract source-discovery topics.
- Rewrite target artifacts in this repository's architecture and voice.

Forbidden:

- Copy external repository prose verbatim.
- Copy external source code into runtime modules.
- Promote dated checklist advice into enforced rules without primary-source confirmation.
- Commit credentials, private client data, or live-provider exports.
- Add files that are not connected to agents, skills, workflows, tests, registries, or docs.

## Inventoried Sources

| Source | Observed HEAD | Use type | Primary value |
|---|---:|---|---|
| `joshbuchea/HEAD` | `de1304e` | rule-candidate | HTML head and metadata rules |
| `danishashko/geo-aeo-tracker` | `08a997d` | knowledge | GEO, AEO, SRO, and AI visibility heuristics |
| `every-app/open-seo` | `61c0b0c` | workflow-pattern | MCP-style SEO workflows and agent patterns |
| `marcobiedermann/search-engine-optimization` | `a4681ed` | rule-candidate | Broad SEO checklist candidates |
| `bmpi-dev/awesome-seo` | `6537646` | source-index | Crawl, log, tool, international, and learning source discovery |
| `garmeeh/next-seo` | `f74b86b` | implementation-reference | Next.js metadata and JSON-LD patterns |
| `iamvishnusankar/next-sitemap` | `144fad9` | implementation-reference | Next.js sitemap and robots patterns |
| `kjvarga/sitemap_generator` | `b7bcd69` | implementation-reference | Sitemap extension patterns |
| `goenning/google-indexing-script` | `c52c2f8` | adapter-hardening | Indexing API implementation patterns |
| `stevenvachon/broken-link-checker` | `ce9e116` | adapter-hardening | Broken-link crawler edge cases |

## Phase Status

| Phase | Unit | Status |
|---:|---|---|
| 1 | Source governance and inventory | verified |
| 2 | HEAD metadata rules | verified |
| 3 | GEO/AEO/SRO upgrade | verified |
| 4 | OpenSEO workflow expansion | verified |
| 5 | Checklist, crawl budget, and logfile reference expansion | verified |
| 6 | Explicit Phase 7-10 split checkpoint | verified |
| 7 | Framework implementation notes | verified |
| 8 | Adapter hardening | verified |
| 9 | Registry and cross-linking | verified |
| 10 | Final verification and rebaseline | verified |

## Verification Gates

Each phase must pass its matrix verification commands and any touched canonical checks. A phase is
not verified until its tests pass and the matrix status is updated to `verified`.
