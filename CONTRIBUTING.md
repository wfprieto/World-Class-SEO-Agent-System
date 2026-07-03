# Contributing

## Contribution Standard

Every contribution must improve the system's SEO capability, operating clarity, evidence quality, safety, or implementation usefulness.

## Required for Agent Changes

- Keep the agent name stable.
- Define mission, ownership, evidence, skills, outputs, forbidden actions, and handoffs.
- Update `agents/AGENT_INDEX.md` if routing changes.
- Preserve model agnosticism.

## Required for Skill Changes

- Define purpose, inputs, outputs, and quality gate.
- Update `skills/SKILL_INDEX.md`.
- Avoid duplicating another skill.

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

