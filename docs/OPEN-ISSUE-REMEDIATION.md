# Open-Issue Remediation

This document explains the executable remediation program for issues #26, #28, #29, #30,
#31, and #32. The authoritative contract is `governance/open-issue-remediation.json`; its schema
and validator fail closed on missing issue bindings, ambiguous classifications, unsafe evidence
paths, unsupported owner transitions, or recurring controls represented as ended when their
implementation tickets close.

The program covers code and repository-controlled evidence. Packaging and release maturity,
demonstrated real-world effectiveness, provider outcomes, rankings, traffic, adoption, and
community effectiveness are not silently treated as code-complete.

## Execution matrix

| Issue | Classification | Executable outcome | Closure boundary |
|---|---|---|---|
| #26 | Bounded debt | Every exact reauthorized import edge has one owner, retirement plan, acceptance condition, review window, and verification command. | Close after the exact non-broadening P10 reauthorization passes; the dated retirement plans remain enforceable. |
| #28 | Code capability | Every repository-controlled gap has existing source and automated-test receipts; live-provider and excluded gaps remain explicit. | Close when all `CODE_REMEDIATION` rows are resolved without changing scores or live-evidence state. |
| #29 | Recurring control | Scheduled maintenance checks knowledge, locks, governance, comparative state, architecture debt, and mutations. | Close the implementation ticket while the `CONTINUOUS` maintenance control remains active. |
| #30 | Owner action | Authenticated provider evidence binds one monitored private conduct destination, public disclosures, and rollback. | Close after the READY contract and linked operations checks pass at the merged commit. |
| #31 | Recurring control | Exact-head CI, immutable actions, locked dependencies, source integrity, rollback tests, and scheduled drift checks remain executable. | Close the implementation ticket while the `CONTINUOUS` certification and rollback control remains active. |
| #32 | Recurring control | Schema, evidence-binding, report, receipt, and security mutation controls run in certification and scheduled maintenance. | Close the implementation ticket while the `CONTINUOUS` integrity control remains active. |

## Required operating loop

1. Work from a clean short-lived branch based on current `main`.
2. Add or update a failing mutation test before weakening or extending a control.
3. Run the focused acceptance commands recorded for the affected issue.
4. Run `seoctl system doctor` on Python 3.11, 3.12, or 3.13 and the full repository validator.
5. Require exact-head GitHub certification and resolve review findings before squash merge.
6. Verify the resulting `main` commit and attach non-sensitive evidence to the bound issue.
7. Revert the bounded change using the recorded rollback procedure if any required gate regresses.

Scheduled workflows are drift detectors, not self-modifying bots. They have read-only permissions
and never refresh dates, rewrite evidence, change GitHub settings, or close issues.

## Private conduct prerequisite

Issue #30 is `READY` because all of the following are bound:

- the owner-selected private destination `wfprieto@gmail.com`, distinct from public issues,
  Discussions, and vulnerability intake;
- authenticated Gmail-profile access evidence for the accountable maintainer without mailbox
  contents;
- updated `SUPPORT.md` and `CODE_OF_CONDUCT.md` instructions;
- a 72-hour acknowledgement target, monitoring role, confidentiality limits, and conflict
  handling; and
- passing repository-operations, remediation-contract, and private-intake validation.

The canonical state is `governance/private-conduct-intake.json`. READY requires a real mailto
destination, owner-authorized publication, authenticated-provider profile digest, provider access
method, and the exact prohibited-data boundary. Repository comments, commits, self-authored
assertions, and example destinations cannot replace provider evidence.

Use the ongoing verification checklist in
[`docs/REPOSITORY-OPERATIONS.md`](REPOSITORY-OPERATIONS.md#owner-verification-and-recovery-checklist).
If authenticated access or monitoring later fails, remove the public instructions, restore
`BLOCKED_OWNER_ACTION`, preserve no report contents in repository evidence, and reopen issue #30.
