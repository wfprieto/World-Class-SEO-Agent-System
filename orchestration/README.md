# Orchestration

This directory defines how agents share state, pass handoffs, and resolve decisions during multi-agent SEO work.

## Core Contracts

- `session-state.schema.json`: shared workflow state.
- `schemas/handoff-payload.schema.json`: agent-to-agent handoff payload.
- `schemas/decision-record.schema.json`: decision and debate outcome.
- `schemas/agent-output.schema.json`: standard agent output.

## Orchestration Rules

1. The lead agent owns the workflow outcome.
2. Supporting agents write outputs to session state.
3. Any handoff must use the handoff payload fields.
4. Critical or high-risk work must pass through SEO Scrummaster Agent.
5. Missing evidence lowers confidence and may block implementation.
6. The Senior SEO Strategist Agent owns sequencing after findings are accepted.
7. The Senior SEO Engineer Agent owns implementation only after acceptance criteria are clear.

## Failure Handling

If required evidence is missing:

- Mark evidence status as `missing` or `partial`.
- Lower confidence.
- Continue only with safe diagnostic work.
- Do not implement high-risk changes.

If agents disagree:

- Invoke SEO Scrummaster Agent.
- Create a decision record.
- Resolve as Approve, Revise, Reject, or Defer.

If implementation risk is high:

- Require rollback plan.
- Require verification method.
- Require human approval before deployment.

