# Specialist Decision Standard

This is the shared decision contract for high-risk SEO specialists. Domain rules belong in `skills/specialist-depth-playbooks.md` and canonical skill definitions; do not duplicate them here or in agent role files.

## Decision states

- `READY`: required evidence is current, attributable, and sufficient for the bounded decision.
- `PARTIAL`: some checks are valid, but named missing evidence limits coverage or confidence.
- `BLOCKED`: a required source, authorization, identity, jurisdiction, baseline, or safe execution path is absent.
- `ABSTAIN`: evidence cannot distinguish competing explanations or the requested conclusion exceeds the specialist's authority.
- `ESCALATE`: credible material harm, security, accessibility, legal, policy, privacy, or sitewide-change risk requires the named human or specialist owner.

Runtime mapping is exact: `READY` maps to `COMPLETE`; `PARTIAL` and `ABSTAIN` map to `PARTIAL`;
`BLOCKED` and `ESCALATE` map to `BLOCKED`. An escalation therefore suppresses dependent nodes and
cannot produce a complete workflow until the required human action is resolved and the specialist
is rerun.

`PARTIAL` never silently becomes `READY`. `BLOCKED` and `ABSTAIN` are valid outcomes, not failures to be hidden.

## Evidence sufficiency

Before deciding, record the decision question, scope, source, capture time, method, coverage, identity resolution, authorization mode, and material limitations. Separate:

1. observed fact;
2. supported analysis;
3. competing hypothesis;
4. unknown or untested condition;
5. recommended verification.

One observation may establish that an event occurred; it does not establish prevalence, cause, trend, compliance, conformance, or business impact. Missing evidence is `UNKNOWN`, never a pass or failure.

## Decision procedure

1. Resolve the target entity, page, market, asset, claim, or incident before comparison.
2. Select only the canonical skills needed for the decision.
3. Apply the domain playbook's evidence gate before scoring or recommending action.
4. Test plausible benign and harmful explanations against the same evidence.
5. Prefer reversible monitoring or verification when evidence does not justify intervention.
6. Emit one decision state with evidence IDs, confidence rationale, owner, acceptance criteria, and verification method.
7. Hand off rather than crossing another agent's responsibility or a human-only approval boundary.

## Failure, abstention, and escalation

- Preserve valid partial evidence after a source, viewport, provider, or market fails; name failed coverage.
- Abstain from causal, legal, accessibility-conformance, attribution, intent, or market-wide conclusions that the evidence cannot support.
- Never fabricate a baseline, source, identity, authorization, translation review, jurisdiction, measurement, transcript, or competitor motive.
- Escalate before disavow submission, security containment, legal approval, regulated-claim publication, hidden-address disclosure, bulk international changes, or destructive/indexation-wide changes.
- A fallback must narrow the claim and coverage. It must not present a weaker method as equivalent execution.

## Edge-case discipline

Explicitly evaluate stale, duplicated, sampled, localized, personalized, inaccessible, contradictory, partial, and provider-limited evidence. Preserve intentional variations and distinguish unavailable, not observed, not applicable, and failed checks.

## Example contract

Good: "`PARTIAL`: 14 injected URLs were observed in a dated index sample, but server logs and security-console access are unavailable. Escalate containment review; do not attribute an attacker or submit a disavow."

Bad: "The competitor attacked the site; disavow every low-authority link."

Examples constrain reasoning but are not evidence for a live finding.

## Bounded integrity guarantee

`governance/specialist-playbook-integrity.json` binds this standard and each priority specialist's
exact playbook section to a reviewed version and normalized UTF-8 SHA-256 digest. Static validation
and runtime decision artifacts consume the same registry. This proves exact canonical loading and
the deterministic known-answer mappings; it does not prove semantic understanding, model
compliance, diagnostic accuracy, or real-world SEO effectiveness.
