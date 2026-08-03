# Contributing

## Contribution Standard

Every contribution must improve the system's SEO capability, operating clarity, evidence quality, safety, or implementation usefulness.

## Operational traceability

Every material contribution must identify:

- the applicable control ID from `governance/repository-operations.json` and
  [`docs/REPOSITORY-OPERATIONS.md`](docs/REPOSITORY-OPERATIONS.md);
- the accountable owner and provider-verified backup status;
- the canonical issue and authority changed;
- the evidence class and exact source or test;
- the verification command and observed result;
- the rollback trigger, recovery procedure, and stop condition; and
- confirmation that no credential, private URL, client data, vulnerability detail, or private
  conduct report appears in public material.

Use `UNMAPPED` only to request maintainer triage; it is not evidence that a critical path is out
of scope. A role label does not prove that a distinct backup exists.

## Required for Agent Changes

- Keep the agent name stable.
- Define mission, ownership, evidence, skills, outputs, forbidden actions, and handoffs.
- Update `agents/AGENT_INDEX.md` if routing changes.
- Preserve model agnosticism.

## Required for Skill Changes

- Define purpose, inputs, outputs, and quality gate.
- Update `skills/SKILL_INDEX.md`.
- Avoid duplicating another skill.
- Follow `skills/skill-definition-standard.md`.
- Include Purpose, System Prompt, Required Inputs, Execution Steps, Output Format, Quality Gate, Failure Conditions, and Fallback.
- Link to a template or schema when the skill produces a durable deliverable.

## Required for Workflow Changes

- State the lead agent.
- State supporting agents.
- Define the definition of done.
- Include escalation rules where risk exists.

## Required for Knowledge Changes

- Prefer official or first-party sources.
- Add confidence level if the source is not official.
- Use `schemas/rule-update.schema.json` for new system rules.

## Prohibited Contributions

- Manipulative link schemes
- Doorway page systems
- Fake reviews or fake locations
- Hidden text or cloaking
- Unsupported ranking-factor claims
- Model-specific lock-in outside `Codex.md` and `ChatGPT.md`
