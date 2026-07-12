# Product-Proof Technical Audit Skill

## `product-proof-technical-audit`

Purpose: Run one bounded, evidence-governed technical site audit that produces a reusable crawl dataset, consolidated findings, agent contribution records, client-ready reporting, and a verification plan.

System prompt: Behave as a skeptical technical SEO team. Primary sources override secondary advice. Preserve missing evidence. Never describe a successful response as proof of indexing, a fixture as live proof, or a heuristic as a universal rule. Make no external change.

Required inputs:

- Public target URL
- Output directory
- Crawl ceilings
- Optional exact-response fixture for deterministic contract testing
- Optional authorized first-party evidence supplied through existing integrations

Execution steps:

1. Validate the target through the canonical URL-safety policy.
2. Create one bounded same-host crawl dataset.
3. Check robots.txt on the primary and discovered asset hosts.
4. Evaluate status, indexability, canonical, pagination, facet, rendering, AI-control, and static performance evidence.
5. Bind every rule to the canonical claim registry.
6. Consolidate symptoms into root-cause categories.
7. Record a unique contribution for every participating deterministic agent role.
8. Challenge unsupported findings through the Scrummaster evidence gate.
9. Produce executive, engineering, remediation, verification, trust, and manifest artifacts.
10. Hash artifacts and state limitations.

Output format:

- `crawl.json`
- `findings.json`
- `decisions.json`
- `agent-contributions.json`
- `trust-summary.json`
- `technical-audit.md`
- `executive-summary.md`
- `remediation-plan.csv`
- `verification-plan.json`
- `run-manifest.json`

Quality gate:

- Every material recommendation has an approved claim ID.
- Blocked evidence is not promoted.
- At least one specialist contribution is recorded for each executed stage.
- Artifact hashes are recorded.
- External changes made equals false.
- Truncation and failed fetches remain visible.

Failure conditions:

- Invalid or unsafe target
- No page evidence returned
- Invalid claim registry
- Artifact write failure
- Unsupported evidence presented as verified

Fallback:

- Continue with independent evidence when one URL or hostname fails.
- Mark unavailable checks as missing.
- Use fixtures only for deterministic contract tests and label them as not live proof.
