# Comprehensive Remediation Delivery Record

## Phase contract

- **Objective:** Correct the repository review findings without weakening the evidence-first SEO mission or introducing a competing command, evidence, routing, or evaluation authority.
- **Scope:** CLI discovery and onboarding; comparative current-state truth; risk-weighted verification; packaging and Python-support consistency; behavior-preserving module boundaries; release evidence; post-merge branch hygiene.
- **Non-goals:** Fabricating authorized live-site results, provider credentials, independent reviewer verdicts, adoption outcomes, production deployment, or a public superiority claim.
- **Owner:** Repository maintainer (`@wfprieto`) retains release and external-evidence authority. The remediation branch owns source and automated-test evidence only.
- **Baseline:** `main` at `1dbfc232eb8b8540f2f5a3e5f79fabe54874531d`; GitHub Actions run `30681366958` passed; local suite passed 355 tests on Python 3.14.5 with 74% aggregate branch coverage; official CI covers Windows and Ubuntu on Python 3.11 and 3.13.
- **Known risks:** Comparative artifacts are stale; root CLI help hides registered families; live provider and external reproduction evidence remains unavailable; several operational modules have lower coverage than the aggregate; no tagged GitHub release exists.
- **Acceptance evidence:** Focused regression tests for each corrected failure mode, complete local suite, repository validators, type/lint gates, clean build/install checks, exact-commit GitHub CI after push, and an independent Senior Scrum Master III challenge.
- **Rollback:** Revert the remediation commit or close the draft pull request. No database migration, provider mutation, credential change, deployment, or production data operation is in scope.

## Learning records

Automated evidence, GitHub CI, deployed/provider evidence, and operational outcomes remain separate evidence classes.

1. **CLI discovery:** Root help had drifted from the 67-command registry even though family parsers worked. Root help and family dispatch now derive from the canonical registry; the registry remains the command authority.
2. **Comparative truth:** Narrative capability claims can remain stale after code lands. Comparative records now pin reviewed Git ancestry and SHA-256 digests of both canonical inventories, and fail on inventory contradictions. The historical 69.9 score was deliberately not inflated without a new scored evaluation.
3. **Risk verification:** A 65% aggregate coverage floor hid weaker provider and network boundaries. Six risk-specific floors now supplement, rather than replace, the aggregate gate.
4. **Packaging:** A successful source checkout is not clean-install evidence. CI now verifies the exact built wheel on Windows and Ubuntu with Python 3.13, and the local Python 3.13 clean-wheel fixture completed successfully.
5. **Dependency control:** Broad development ranges were not reproducible. `requirements-dev.in` is now the canonical direct constraint set, with a generated transitive lock and a validator that rejects a missing generated header, duplicate pins, unpinned direct requirements, invalid direct versions, and direct pins outside the declared constraints.
6. **Architecture:** Large mixed-responsibility modules obscured pure validation and parsing boundaries. Content analysis, technical parsing, authority drift, and evidence integrity are now isolated while service classes, persisted formats, and compatibility imports remain unchanged.
7. **Release integrity:** Build evidence existed only as CI artifacts. A tag-triggered workflow now fails closed on release readiness, produces checksums and CycloneDX evidence, generates GitHub build/SBOM attestations, and publishes only after all gates pass.
8. **CI ancestry:** Comparative freshness checks require the pinned baseline commit to exist locally. The first draft-PR run exposed the default shallow checkout; validation jobs now fetch complete history and a regression test protects that prerequisite.
9. **Cross-platform inventory hashing:** The second draft-PR run exposed CRLF/LF byte drift in otherwise identical registry JSON. Inventory pins now normalize only line endings before SHA-256 hashing, with an explicit portability regression.

## Twenty-pass integration record

| Pass | Focus | Result |
|---:|---|---|
| 1 | Mission and scope | Preserved evidence-first, read-only-by-default SEO operation and explicit external mutation gates. |
| 2 | Source-of-truth authority | Kept one command registry, capability registry, evidence store, and family parser authority. |
| 3 | CLI discoverability | Exposed all registry families and actions through root help. |
| 4 | First-run journey | Added install, quickstart, fixture-audit, and expected-artifact guidance. |
| 5 | Comparative provenance | Added ancestry and canonical-inventory digest checks. |
| 6 | Claim discipline | Removed resolved gaps without inventing a new score or live superiority proof. |
| 7 | Dependency reproducibility | Added canonical input, generated lock, and semantic constraint validation. |
| 8 | Runtime compatibility | Aligned metadata and CI on Python 3.11 through 3.13. |
| 9 | Cross-platform CI | Expanded validation to Windows and Ubuntu across three Python versions. |
| 10 | Aggregate testing | Combined suite passed 402 tests with 78.48% branch coverage locally on Python 3.14.5. |
| 11 | Risk-weighted coverage | All six boundary floors passed, from 64.50% to 87.13% as configured. |
| 12 | Static correctness | Ruff correctness rules, compileall, and mypy passed across runtime and release surfaces. |
| 13 | Security regression | Secret scanning and the mutation probe passed. |
| 14 | Evidence integrity | Pure digest/decode boundary extracted with forged, malformed, and non-object adverse tests. |
| 15 | Technical parsing | Pure robots, HTML, schema, and performance parsing extracted with adverse tests. |
| 16 | Content analysis | Pure bounded validation and text analysis extracted with regression tests. |
| 17 | Authority drift | Drift lifecycle extracted while preserving import identity and database authority. |
| 18 | Distribution | sdist and wheel built; the supported Python 3.13 clean-wheel audit passed. |
| 19 | Supply-chain release | Dependency audit found no known vulnerabilities; release checksums and attestations are automated. |
| 20 | Truthful closeout | Local source evidence is green; exact-commit CI, authorized live providers, independent external reproduction, tag, release, deployment, and adoption remain separate gates. |

## Unresolved risks and next evidence

- **Exact-commit CI — owner `@wfprieto`; next action 2026-08-01:** Push the remediation branch, observe the six-cell and certification jobs, and record the immutable run URL/SHA. Local success is not CI proof.
- **Authorized live verification — owner `@wfprieto`; next review 2026-08-08:** Select an owned test property, approve provider scope/cost, and run the documented smoke plan. No provider mutation was attempted here.
- **External reproduction and outcomes — owner `@wfprieto`; next review 2026-08-15:** Commission a clean external install and seven-archetype benchmark. Real-user adoption and superiority outcomes remain unproven.
- **Public release — owner `@wfprieto`; next action only after all gates pass:** Keep `release_decision` `BLOCKED`; the release workflow is machinery, not evidence that a tag or release exists.
- **Remote branch hygiene — owner `@wfprieto`; next action after draft PR creation:** Recheck merged PR ancestry immediately before deleting only the four recorded stale branch refs.
