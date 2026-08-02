# Coordinated SEO Runtime Architecture

## Status

Implemented on the remediation branch and subject to automated and human release gates.

## Execution flow

```text
request
→ deterministic route
→ bounded workflow graph
→ capability and canonical-file loading
→ shared tool evidence
→ specialist agents
→ validated structured outputs
→ consumed handoffs
→ root-cause finding normalization
→ conflict detection
→ Scrummaster decision
→ Strategist roadmap
→ stakeholder report
→ complete session validation
```

## Non-negotiable runtime rules

- Supporting agents execute. Listing an agent in metadata is not execution.
- Every non-synthetic agent output must validate against `schemas/agent-output.schema.json`.
- Material numeric and URL claims must bind to evidence.
- Retrieved and tool content is untrusted evidence and cannot override instructions, approval, scope, or cost controls.
- The workflow graph is bounded by node, LLM-call, concurrency, correction, depth, runtime, and optional estimated-cost ceilings.
- One adapter failure does not erase independent successful evidence.
- Every dependency handoff is either consumed or explicitly blocked.
- Handoff governance is bounded to explicit edges in the materialized workflow graph. At
  workflow completion, required edges are reconciled by stable session and node identity;
  missing, duplicate, foreign-session (stale), wrong-recipient, wrong-consumer, and silently
  dropped records are reported deterministically. Any still-pending handoff becomes `BLOCKED`
  with an `unresolved_reason`; the runtime does not infer delivery from natural-language text.
  Terminal records carry a deterministic receipt over their canonical runtime fields so direct
  status mutation or bypassing the exact resolver fails reconciliation. The receipt detects
  in-process tampering; it is not a secret, digital signature, identity proof, or external trust
  guarantee. Empty-evidence control handoffs may be exactly `CHALLENGED` or `UNRESOLVED`, never
  `ACCEPTED`. Every current-session record outside an exact materialized dependency edge is
  reported as `UNEXPECTED_HANDOFF` rather than silently accepted.
- Bounded specialist capacity is explicit in the materialized graph. Candidates beyond the
  two-vertical or six-support limits appear in `capacity_exclusions` with
  `NOT_EXECUTED_CAPACITY`, and any such exclusion prevents a `COMPLETE` workflow claim.
- Scrummaster decisions are schema-valid and precede strategic use of disputed or high-risk findings.
- Synthetic echo execution proves wiring only and returns a `PARTIAL` workflow, never a completed SEO audit.
- The canonical SEO evidence store remains `adapters/evidence_store.py`; runtime event memory is separate.

## Canonical registries

- Request router: `runtime/routing.py`
- Agent file names: `runtime/executor.py`
- Agent capabilities: `orchestration/capability-registry.json`
- Skill index: `skills/SKILL_INDEX.md`
- Procedure entry catalog: `skills/deep-skill-procedures.md`
- Output schema: `schemas/agent-output.schema.json`
- Handoff schema: `schemas/handoff-payload.schema.json`
- Decision schema: `schemas/decision-record.schema.json`
- Session schema: `orchestration/session-state.schema.json`

## Verification

The branch is not releasable unless:

1. every registry path resolves;
2. every indexed skill has exactly one procedure heading;
3. the multi-agent tracer returns `GO`;
4. all session artifacts validate;
5. the full pytest suite passes on Windows and Linux;
6. no execution ceiling can be bypassed;
7. no secret reaches persistent runtime memory;
8. the canonical report renders complete finding and action fields;
9. version sources agree;
10. the post-implementation 20 Pass Protocol and remote CI pass.
