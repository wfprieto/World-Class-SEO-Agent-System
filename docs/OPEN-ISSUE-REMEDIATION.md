# Open-Issue Remediation

This document explains the executable remediation program for issues #26, #28, #29, #30,
#31, and #32. The authoritative contract is
`governance/open-issue-remediation.json`; its schema and validator fail closed on missing issue
bindings, ambiguous classifications, unsafe evidence paths, erased owner blockers, or recurring
controls represented as one-time work.

The program covers code and repository-controlled evidence. Packaging and release maturity,
demonstrated real-world effectiveness, provider outcomes, rankings, traffic, adoption, and
community effectiveness are not silently treated as code-complete.

## Execution matrix

| Issue | Classification | Executable outcome | Closure boundary |
|---|---|---|---|
| #26 | Bounded debt | Every exact reauthorized import edge has one owner, retirement plan, acceptance condition, and verification command. | Close only after the exception set reaches zero and the architecture validator passes without a broadened allowlist. |
| #28 | Code capability | Every open capability has a typed disposition, owner, next action, acceptance criteria, and evidence boundary. | Close when all `CODE_REMEDIATION` rows are verified or truthfully rejected; external and excluded rows remain explicitly classified. |
| #29 | Recurring control | A weekly and manually dispatchable maintenance workflow checks knowledge, locks, governance, comparative state, architecture debt, and mutations. | Keep open as the recurring maintenance record. |
| #30 | Owner action | Documentation and validators preserve the truthful private-conduct blocker and prevent the vulnerability route from masquerading as conduct intake. | Close only after the owner designates and attests one monitored private destination. |
| #31 | Recurring control | Exact-head CI, immutable actions, locked dependencies, source integrity, rollback tests, and scheduled drift checks remain executable. | Keep open as the recurring certification and rollback record. |
| #32 | Recurring control | Schema, evidence-binding, report, receipt, and security mutation controls run in certification and scheduled maintenance. | Keep open as the recurring integrity record. |

## Required operating loop

1. Work from a clean short-lived branch based on current `main`.
2. Add or update a failing mutation test before weakening or extending a control.
3. Run the focused acceptance commands recorded for the affected issue.
4. Run `seoctl system doctor` on Python 3.11, 3.12, or 3.13 and the full repository validator.
5. Require exact-head GitHub certification and resolve review findings before squash merge.
6. Verify the resulting `main` commit and attach non-sensitive evidence to the bound issue.
7. Revert the bounded change using the recorded rollback procedure if any required gate regresses.

The scheduled maintenance workflow is a drift detector, not a self-modifying bot. It has read-only
permissions and never refreshes dates, rewrites evidence, changes GitHub settings, or closes issues.

## Private conduct prerequisite

Issue #30 is intentionally `BLOCKED_OWNER_ACTION`. A valid transition requires all of the
following:

- one owner-selected destination that is private and distinct from public issues and Discussions;
- confirmed monitoring and access by the accountable maintainer;
- updated `SUPPORT.md` and `CODE_OF_CONDUCT.md` instructions;
- non-sensitive attestation evidence linked from the operations registry; and
- passing repository-operations, remediation-contract, and provider-authentication validation.

Until then, no personal address is invented or published and the private vulnerability form is
not described as a conduct-reporting channel.

The canonical state is `governance/private-conduct-intake.json`. This schema version permits only
`BLOCKED_OWNER_ACTION`: it requires no destination, monitoring claim, access-test claim,
acknowledgement target, or closure evidence. Repository commits, issue comments, self-authored
assertions, and example or test destinations are not operational verification and cannot promote
the control. A future schema may add an operational state only together with provider-controlled,
immutable verification of the real destination and access test. Its public instructions must state
the acknowledgement target, monitoring role, confidentiality limits, and conflict handling.

Use the owner provisioning checklist in
[`docs/REPOSITORY-OPERATIONS.md`](REPOSITORY-OPERATIONS.md#owner-provisioning-checklist). The
repository may enforce the blocked-state checklist but cannot choose the destination, authorize
its publication, prove mailbox or service access, or make the owner's monitoring commitment.
