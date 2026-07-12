# Comparative Improvement Loop

## Purpose

Improve one verified capability gap at a time while preserving the World-Class runtime architecture and comparing the result against a pinned Claude SEO baseline.

The loop is controlled. It may prepare branches, tests, evidence and review packages. It may not silently modify `main`, change its own scoring rules, approve its own work or merge without the normal repository workflow.

## Lead and reviewers

- Builder: assigned senior engineer or implementation agent
- Adversarial process reviewer: Senior ScrumMaster 3
- Architecture and release reviewer: VP Engineering
- Merge authority: repository owner or explicitly authorized human-controlled merge workflow

## Required states

```text
DISCOVER
→ BASELINE
→ HYPOTHESIS
→ RED_VERIFIED
→ IMPLEMENTED
→ VERIFIED
→ COMPARED
→ UNDER_REVIEW
→ APPROVED_GREAT | REWORK_REQUIRED | REJECTED_BAD | ARCHITECTURAL_REDESIGN
```

## Step 1: Discover

Select exactly one `GAP_OPEN` row from `evaluation/comparative/capability-parity.json`.

Confirm:

- target commit;
- pinned Claude commit;
- exact current behavior;
- exact comparator behavior;
- licensing and provenance;
- affected agents, skills, tools and documentation;
- likely security, cost and operational risks.

Do not choose work because it adds the most files. Choose the smallest complete capability that closes a material outcome gap.

## Step 2: Baseline

Record identical task inputs and measures for both systems.

At minimum compare:

- functional completion;
- accuracy;
- evidence quality;
- failure handling;
- security;
- cost control;
- cross-platform behavior;
- installation;
- documentation;
- maintainability;
- agent integration.

The comparator commit is frozen for the cycle.

## Step 3: Hypothesis

State why the proposed correction should reach parity or superiority and why it belongs in the architecture.

The hypothesis must name:

- the user-visible outcome;
- the canonical interface;
- preserved behavior;
- test boundary;
- expected evidence;
- rollback.

## Step 4: RED verified

Write failing tests before production code.

The RED record includes:

- test file;
- test name;
- behavior;
- command;
- actual failure;
- implementation file driven by the test.

Do not create a test that merely checks for a file name or marketing phrase when the gap is functional.

## Step 5: Implement

Implement the minimum complete correction.

Every new capability must connect through the existing architecture:

```text
agent
→ capability registry
→ command or adapter
→ bounded tool dispatch
→ normalized evidence
→ schema-valid output
→ handoff and synthesis
```

No capability may bypass:

- RunBudget;
- URL safety;
- credential redaction;
- evidence binding;
- ToolDispatcher;
- session validation;
- approval gates.

## Step 6: Verify

Run:

- focused tests;
- full tests;
- supported OS and Python matrix;
- security tests;
- cost and timeout tests;
- documentation commands;
- installer and removal tests where applicable;
- fixture tests;
- authorized sandbox smoke test when live proof is required.

A mock does not prove a live integration.

## Step 7: Compare

Run the same benchmark task against the pinned Claude capability and the target correction.

Rate the correction:

- `GREAT`: parity or superiority, all gates pass, no material unresolved objection;
- `GOOD`: useful but incomplete or still inferior;
- `BAD`: regressive, unsafe, cosmetic, duplicated or unjustified.

The builder rating is not an approval.

## Step 8: Independent review

Create one immutable evidence package hash.

Senior ScrumMaster 3 and VP Engineering review that exact package in separate fresh contexts. They cannot see each other's verdict before submission.

One `REJECT_BAD` blocks the cycle. One `REWORK_GOOD` continues the loop. Both must return `APPROVE_GREAT` to close the capability.

## Step 9: Learn

Lessons persist only after `APPROVE_GREAT`.

A lesson must become one of:

- a test;
- a schema rule;
- a canonical integration contract;
- an ADR or decision record;
- a validated reusable implementation pattern.

Do not persist unverified model opinion as system knowledge.

## Step 10: Repeat or release

Normal correction is limited to five iterations.

After five non-great iterations, stop incremental patching and enter `ARCHITECTURAL_REDESIGN`.

The loop never changes the scoring formula to manufacture success.

## Definition of done

A capability row closes only when:

- tests pass with no regressions;
- required live evidence is verified;
- target is at parity or superior to the pinned comparator;
- security, cost, installation, documentation and rollback gates pass;
- both independent reviewers return `APPROVE_GREAT`;
- the parity ledger links the evidence;
- the normal PR and merge workflow completes.
