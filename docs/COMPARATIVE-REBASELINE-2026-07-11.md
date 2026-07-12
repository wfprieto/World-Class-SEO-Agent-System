# Comparative Rebaseline: World-Class SEO vs Claude SEO

**Date:** 2026-07-11  
**Target:** `wfprieto/World-Class-SEO-Agent-System@8e6f666506ff723eb6f8f354e4150b30073fb67f`  
**Comparator:** `AgriciDaniel/claude-seo@6cf1ea9fe4c2088b2ad3089797f846850fd66164`  
**Comparator license:** MIT  
**Scoring formula:** `sum((score / 10) * weight)`

## Verdict

The target has the stronger runtime and governance architecture. Claude SEO remains the stronger finished operator product because it exposes a wider execution command surface, more live integrations, deeper skill-coupled references, more complete onboarding and a mature public release ecosystem.

The current evidence-based weighted score is:

| System | Weighted score |
|---|---:|
| World-Class SEO Agent System | 69.9 / 100 |
| Claude SEO | 80.0 / 100 |
| Current gap | 10.1 points |
| Required target | 92.0 / 100 |

This score is lower than the supplied 73/100 assessment because the supplied category values and weights did not mathematically reproduce its final total. The rebaseline uses one explicit formula and enforces it in tests. Agent depth is capped at 8.9 because its evidence maturity is `LIVE_CAPABLE`, not yet `PRODUCTION_READY` under the immutable scoring rules.

## What changed after the supplied assessment

The following original criticisms are now stale or materially reduced:

- Supporting agents are no longer metadata only. They execute in a bounded DAG.
- Handoffs are consumed and decision records are validated.
- Material factual claims are evidence bound.
- Business-profile resolution affects specialist composition.
- CI runs on Windows and Ubuntu with Python 3.11 and 3.13.
- The changelog contains substantive release history.
- README includes Start Here and executable runtime examples.

These improvements do not close the decisive product gaps.

## Remaining critical gaps

### 1. Execution tooling

The runtime can coordinate more safely than Claude SEO, but it cannot yet collect and analyze the same breadth of evidence automatically. The project needs a coherent operator command layer rather than a loose expansion of unrelated scripts.

### 2. Live integrations

Most current adapters normalize user-supplied exports. Production connectors, installer paths, credential checks, health checks and authorized smoke-test evidence remain incomplete.

### 3. Skill packaging and references

The system has strong canonical governance, but many skills remain grouped definitions with uneven reference depth. High-value executable skills need independent packages without recreating the duplicate-rule problem already removed.

### 4. Content intelligence

Content briefing and claims governance are sound, but deterministic quality, verification, entity analysis, content transformation and optional media-generation capabilities remain incomplete.

### 5. Onboarding and ecosystem

The project lacks a clean install-to-report journey, generated command documentation, public release artifacts, issue templates, contributors metadata, CODEOWNERS, citations and platform packaging.

## Anti-bloat decision

Claude SEO's file count is not the target.

The target will use:

- one `seoctl` command surface;
- one capability registry;
- one evidence store;
- one URL-safety policy;
- generated indexes and command documentation;
- optional provider packs outside the core runtime.

A new file is justified only when it creates a testable deletion boundary, independent execution contract or maintainable reference authority.

## Capability ledger

The authoritative gap inventory is:

`evaluation/comparative/capability-parity.json`

Every row must end in one of:

- `VERIFIED_SUPERIOR`
- `VERIFIED_PARITY`
- `INTENTIONALLY_COMBINED`
- `REJECTED_WITH_EVIDENCE`

The final release gate permits no `GAP_OPEN` row.

## Current implementation sequence

1. PR 0: comparative rebaseline and immutable scoring
2. PR 1: controlled improvement loop and independent reviewers
3. PR 2: unified execution CLI and agent entrypoints
4. PR 3: Google first-party integration pack
5. PR 4: rendering and technical execution pack
6. PR 5: content intelligence pack
7. PR 6: authority, media and drift pack
8. PR 7: optional extension ecosystem
9. PR 8: skill and reference restructuring
10. PR 9: content-production prompt pack
11. PR 10: testing, security and observability
12. PR 11: documentation and community infrastructure
13. PR 12: final comparative gauntlet and release

## Release threshold

The remediation is not complete until:

- weighted target score is at least 92;
- no category is below 8;
- tooling, integrations, knowledge and documentation are at least 9;
- the latest pinned Claude baseline is beaten by at least five weighted points;
- the parity ledger has no open row;
- all comparative benchmarks pass;
- Senior ScrumMaster 3 and VP Engineering independently return `APPROVE_GREAT`;
- installation, rollback and release artifacts are proven.
