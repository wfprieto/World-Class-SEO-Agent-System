# Owner-Controlled Remediation Learning Ledger

## Operating contract

- Canonical program: `evaluation/remediation/owner-controlled-remediation-program.json`
- Validator: `scripts/validate_remediation_program.py`
- Baseline: `main` at `e8c37abb5e939d4433e42ea8a02af63549ca0010`
- APIVR tier: Comprehensive; security and data-integrity slices escalate to Forensic.
- Direct merge: forbidden. A normal protected pull request is required.
- Evidence classes remain separate: source, automated, CI, provider, deployed, and operational.
- Excluded from this program: public packaging/release maturity, real-world SEO outcomes,
  external reproduction, adoption, rankings, traffic, conversions, and community-growth claims.

## Phase advancement rule

A later phase may not start until the current phase has:

1. passed every acceptance criterion with evidence;
2. passed focused tests and full repository certification;
3. passed implementation and unexpected-change audits;
4. recorded confirmed learning or `NO_MATERIAL_LEARNING`;
5. resolved every failure with a linked recurrence guardrail;
6. received a fresh-context Senior ScrumMaster acceptance; and
7. received a distinct fresh-context VP Engineering `APPROVE_GREAT` verdict.

The validator enforces these conditions against the canonical program. Reviewers never edit
implementation files, scorecards, phase state, or merge controls.

## Failure-learning record

Use one record for every failed command, test, review, security check, or implementation
assumption that changes the delivery method:

```text
Failure ID:
Phase:
Action:
Expected result:
Observed evidence:
Root cause:
Learning status: confirmed | rejected | unresolved | none
Learning:
Recurrence guardrail:
Verification reference:
Owner:
Due phase:
```

Do not manufacture learning from an environmental interruption or an unrelated failure. If
the root cause remains unknown, record `unresolved` and keep the phase open or blocked.

## Phase 0 - Program controls and current-state audit

### Objective

Create an enforceable remediation loop before implementing feature, architecture, security,
documentation, report, knowledge, or repository-operation changes.

### Scope boundary

Canonical program, baseline, phase order, evidence distinctions, failure learning, independent
review, and rollback. No feature implementation, provider call, production mutation, or direct
merge is in scope.

### Owner and verification

- Owner: Repository maintainer
- Approver: Repository maintainer
- Verifiers: distinct fresh-context Senior ScrumMaster and VP Engineering reviewers
- Rollback: revert the Phase 0 program, schema, validator, tests, and CI invocation together

### Baseline evidence

- `main` commit `e8c37abb5e939d4433e42ea8a02af63549ca0010`
- 404 tests collected
- approximately 78.48 percent aggregate branch coverage
- exact post-merge GitHub Actions run `30717632438` completed successfully

### Frozen audit inventory

The canonical program tracks 15 findings across P0-P8. The immediate critical path is:

- P0: prevent empty-evidence improvement approvals;
- P1: verify private security reporting and protected-main controls;
- P2-P5: enforce product truth, effective registry authority, JSON CLI behavior, and agent differentiation;
- P6: close redirect, credential, retry, side-effect timeout, local privacy, and workflow-integrity gaps;
- P7: correct report execution semantics, fixture labeling, documentation evidence, and source freshness; and
- P8: establish accountable support, conduct, ownership, and repository-operation paths.

Public packaging/release maturity and real-world/external outcome evidence remain excluded even
where older repository artifacts mention them.

### Observed failures and learning

- `AUD-001`: a syntactically valid improvement cycle could contain no changed files, tests,
  evidence references, or lessons and still receive `APPROVE_GREAT` after reviewer hashes were
  recomputed. The reusable guardrail is schema-level `minItems` plus an evaluator defense and a
  forged-hash regression. Local focused verification passes; the finding remains in progress
  until CI observes the committed implementation.
- Two full-suite local runs produced 412 passes and two failures because pytest temporary roots
  were nested inside a parent Git worktree. Git-backed fixture helpers then resolved the parent
  index rather than the isolated fixture. This is classified as a local harness-location
  constraint, not a Phase 0 product regression; exact-commit CI remains the completion evidence.
- The first mypy run found an inferred collection type that was wider than the gate helper's
  declared input. The gate table now has an explicit `dict[str, str | set[str]]` type, and the
  focused mypy gate passes. The recurrence guardrail is to type-check the production validator
  in both local verification and CI.
- The first independent ScrumMaster review rejected the zero-length-only guard because
  whitespace-only array items still produced `APPROVE_GREAT` after hashes were recomputed.
  The recurrence signature is any nominally non-empty evidence field whose normalized value is
  empty. Both schema patterns and evaluator defenses now reject it, with a forged-hash regression.

### Exact-commit and rollback evidence

- Candidate commit: `349e9e66ee8c6937a371e3e78adbd79fb68d64a3`
- Draft pull request: `https://github.com/wfprieto/World-Class-SEO-Agent-System/pull/24`
- Exact-commit CI: `https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/30721534305`
- Matrix result: Windows and Ubuntu on Python 3.11, 3.12, and 3.13 passed.
- Quality/security, Ubuntu and Windows clean-wheel, and aggregate repository-certification jobs passed.
- Rollback rehearsal: a detached worktree at baseline `e8c37abb5e939d4433e42ea8a02af63549ca0010`
  passed `scripts/validate-repository.ps1` and all 10 baseline improvement-loop tests, then the
  temporary worktree was removed through `git worktree remove`.
- Phase 0 remains `IN_PROGRESS` until two new fresh-context canonical verdicts approve the same
  immutable evidence-package hash and the resulting closure commit passes certification.

### Round-two review learning

Both round-two reviewers returned `REWORK_GOOD`. Their counterexamples established that:

- the review hash must bind global scope, APIVR tier, direct-merge policy, every phase contract,
  and the complete audit inventory, while excluding only mutable phase status and verdict storage;
- generic schema-valid reviewer IDs do not establish authority and must resolve through
  `evaluation/reviewer-registry.json`;
- every passing gate needs its own structured evidence rather than a bare status string;
- failure and learning references, commits, and digests require the same validation as acceptance evidence;
- rollback output must persist as a durable artifact; and
- local pytest temporary-root isolation needs an executable detector, not a memory-based convention.

Those controls were implemented at `86bbba3ccd591e0ecc50ec58eaac40f2645f38b5` and passed
exact-commit run `30722374045`, including all matrix, quality/security, clean-wheel, and aggregate
certification jobs. The next review package binds that implementation commit and run.

### Round-three review learning

Both round-three reviewers returned `REWORK_GOOD`. Their adversarial probes demonstrated that
the repository-controlled reviewer registry, generic gate records, mutable failure references,
and a baseline-only rollback check could still overstate closure authority. The corrected control
set now:

- freezes the reviewer registry, verdict schema, and both reviewer instruction identities by
  exact-commit digest and loads reviewer authority from the verified commit;
- authenticates CI records against the canonical repository, workflow, head SHA, conclusion,
  and successful job inventory, while rejecting placeholder URLs;
- requires gate-specific evidence classes and tagged assertions;
- validates failure and learning records at the verified commit or an immutable ancestor;
- rejects pytest roots inside any enclosing Git worktree; and
- binds a durable transcript of an actual newest-to-oldest revert of the complete six-commit
  Phase 0 range from `3fc8320bf2690805ebadbb59057ada76137c11c2` to baseline.

The rollback rehearsal produced a byte-identical baseline, passed repository validation and all
10 baseline improvement-loop tests, and removed the disposable worktree through Git. Phase 0
remains `IN_PROGRESS` pending exact-commit certification of the frozen metadata and two new
fresh-context independent approvals.

The intermediate `baf4cd2` and `ce3df1b` Windows matrices exposed a platform-specific raw-byte
digest defect: Git converted text line endings at checkout, so logically identical rollback
evidence had different hashes. The final executable commit `79f0908bccb271f10b464dd8816f4440347efd04`
canonicalizes CRLF to LF before hashing repository text and includes a direct equivalence
regression. Neither failed run is accepted as evidence.

## Open-issue remediation learning - 2026-08-03

- Failure ID: `OPS-OPEN-001`
- Phase: open issues #26, #28-#32
- Action: run the combined mutation and full test suites on Windows
- Expected result: isolated fixtures and an unchanged zero-debt quality ratchet
- Observed evidence: pytest roots under the repository inherited the enclosing Git index, and
  newly expanded validator functions exceeded the repository's complexity ceiling
- Root cause: the local invocation violated the existing out-of-worktree temporary-root contract;
  new validation branches were initially added before checking the function-span and Ruff ratchets
- Learning status: confirmed
- Learning: local failures must be classified against executable environment contracts before
  changing product code, and control validators must be decomposed before they exceed ratchets
- Recurrence guardrail: full tests use a dedicated system-temp root; scheduled CI uses runner temp;
  Ruff, mypy, and `validate_quality_ratchets.py` run before repository-wide certification
- Verification reference: 975 tests passed from the isolated system-temp root; focused remediation,
  scheduled-workflow, type, lint, quality-ratchet, and full repository validators passed
- Owner: Repository maintainer
- Due phase: complete in this remediation change
