# Product-Proof Intelligence Skills

## `ai-retrieval-timeout-audit`

Purpose: Analyze operator-supplied server logs for AI crawler and user-triggered fetcher timeout evidence.

System prompt: Confirm server semantics, preserve spoofing and correlation limitations, and never claim that a 499 caused exclusion from an AI answer.

Required inputs:

- Server log
- Declared server or proxy stack

Execution steps:

1. Parse bounded log lines.
2. Classify known AI user-agent families.
3. Segment status and response-time evidence.
4. Report 499 rates only with server-specific warnings.
5. Identify affected paths and verification steps.

Output format: request totals, status distribution, response-time summaries, timeout records, warnings, and limitations.

Quality gate: Server stack is recorded; user-agent spoofing and noncausal interpretation are explicit.

Failure conditions: Missing log, missing server stack, unreadable input.

Fallback: Return empty evidence when no recognized requests exist.

## `ai-citation-opportunity-map`

Purpose: Turn dated AI and AI Overview observations into citation, representation, and opportunity evidence.

System prompt: Preserve platform, date, prompt, location/device context, and source. Keep observed, proxy, and modeled impact separate.

Required inputs:

- Dated observation list
- Platform and prompt
- Organic position when available
- AI Overview state and citation state

Execution steps:

1. Validate observation completeness.
2. Calculate prompt coverage, recommendation rate, and linked citation rate.
3. Identify top-ten organic pages that are not cited in an observed AI Overview.
4. Flag inaccurate or misleading brand representation.
5. Preserve competitor and destination evidence.

Output format: observed metrics, unowned opportunities, representation risks, and limitations.

Quality gate: Every record is dated and platform-specific; no universal share-of-voice claim is emitted.

Failure conditions: Undated or malformed observations.

Fallback: Return empty evidence rather than inferred visibility.

## `review-compliance-audit`

Purpose: Screen supplied review-generation and response practices for platform-policy and truth-in-advertising risk.

System prompt: Do not provide legal advice or claim a direct local-ranking effect from review quantity.

Required inputs:

- Review-request practices
- Response coverage
- Platform and jurisdiction context when available

Execution steps:

1. Detect paid, incentivized, self-authored, staff-authored, kiosk, and post-on-behalf practices.
2. Review owner-response and neutral-request coverage.
3. Classify critical, high, and medium risks.
4. Require human platform and jurisdiction review.

Output format: findings, status, actions, observed evidence, and limitations.

Quality gate: Critical risks block approval; no unsupported local-ranking claim appears.

Failure conditions: Missing or malformed practice evidence.

Fallback: Return needs-review when policy context is incomplete.

## `client-performance-narrative`

Purpose: Produce GOOD, BETTER, and BEST reporting language from a baseline, pre-agreed target, actual result, and clearly labeled value model.

System prompt: Do not claim a target was exceeded unless it was established before the period. Do not blend observed, proxy, and modeled evidence.

Required inputs:

- Metric
- Baseline
- Target
- Actual
- Target timing state
- Optional lead value, close rate, and cost

Execution steps:

1. Calculate direction and change.
2. Compare actual with target.
3. Generate factual, trend, and business-value narratives.
4. Label modeled value and ROI.
5. Warn when the target was retrospective.

Output format: GOOD, BETTER, BEST narrative, target state, estimated value, estimated ROI, evidence layers, and limitations.

Quality gate: Modeled values are explicit and target timing is preserved.

Failure conditions: Invalid numeric inputs or missing baseline/target/actual.

Fallback: Produce factual and trend language without a value estimate.
