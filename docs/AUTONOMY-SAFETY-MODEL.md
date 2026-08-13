# Autonomy Safety Model

The public repository defaults to safe autonomy: audit, analysis, recommendations, reports, proof fixtures, and approval-ready plans.

The canonical machine-readable policy is `orchestration/autonomy-safety-policy.json`.

## Modes

| Mode | Name | Meaning |
| --- | --- | --- |
| 0 | Audit Only | Read evidence, run fixtures, produce findings, produce reports. No mutation. |
| 1 | Recommend Only | Prioritize recommendations and action queues. No mutation. |
| 2 | Draft Changes | Draft patches, metadata, content, schema, redirects, or tickets. No application. |
| 3 | Approval-Gated Execution | Apply approved changes only after explicit human approval. |
| 4 | Limited Autopilot | Only pre-approved low-risk actions with rollback and verification. |
| 5 | Full Autopilot Reserved | Reserved for private controlled installations, not the public repo default. |

## Dangerous Actions

These actions always require explicit approval:

- sitewide `robots.txt` changes
- mass `noindex` changes
- canonical rule changes affecting groups of URLs
- redirect migrations
- disavow submissions
- large programmatic page creation
- legal, medical, financial, privacy, or regulated publication
- checkout, lead form, pricing, or revenue-funnel changes
- sending outreach emails or link requests

## Action Queue Rule

Any mutation-capable recommendation must become an action queue item with:

- action ID
- requested mode
- proposed action
- affected URLs or files
- evidence references
- risk class
- approval requirement
- rollback plan
- owner
- verification method
- follow-up trigger or date

## Public Repo Boundary

The public repo may demonstrate autonomy through safe fixtures and local outputs. It must not claim that fixture execution proves live rankings, live indexing, provider authentication, or live website mutation.

## Completion Rule

An autonomous workflow is not complete until it has:

1. evidence,
2. a risk class,
3. an approval decision,
4. a rollback plan when mutation is possible,
5. a verification method,
6. a plain-language report when stakeholders are involved,
7. a learning record when future behavior should change.
