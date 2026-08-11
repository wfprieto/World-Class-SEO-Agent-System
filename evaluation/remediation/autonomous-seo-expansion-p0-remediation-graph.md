# P0 Senior Review Remediation Graph

Program: `autonomous-seo-expansion`  
PR: `#37`  
Rejected reviewed candidate: `1df779a97084db83945128424628257c9a25d6bd`  
Trigger: Senior ScrumMaster 3 pre-review = `REWORK_GOOD`; VP Engineering pre-review = `REWORK_GOOD`  
APIVR tier: `COMPREHENSIVE`

## Objective

Remediate every material reviewer objection without weakening an existing WCSEO quality, evidence, security, rollback, review, or release gate. The remediation is complete only after the new exact candidate passes focused tests, the full canonical CI matrix, a fresh Senior ScrumMaster 3 adversarial re-review, and a fresh VP Engineering adversarial re-review.

## Execution graph

```text
FREEZE REJECTED CANDIDATE 1df779a...
        |
        v
MAP 7 FINDINGS TO FAIL-CLOSED INVARIANTS
        |
        v
WRITE/EXTEND RED TESTS FIRST
        |
        +--> R1 post-review semantic drift
        +--> R2 evidence spoof / candidate mismatch
        +--> R3 positive phase closure + spoof/drift fixtures
        +--> R4 final whole-program closure
        +--> R5 deferred-lane reason/evidence/revisit
        +--> R6 outcome-state normalization
        +--> R7 lifecycle-policy single authority
        |
        v
IMPLEMENT MINIMUM CANONICAL FIXES
        |
        v
FOCUSED TESTS + PROGRAM VALIDATOR
        |
   FAIL? ----YES----> ROOT-CAUSE FIX -> RERUN
        |
        NO
        v
FULL CANONICAL GITHUB CI
        |
   FAIL? ----YES----> ROOT-CAUSE FIX -> NEW HEAD -> FULL CI
        |
        NO
        v
FREEZE NEW REVIEW CANDIDATE
        |
        v
SENIOR SCRUMMASTER 3 BRUTAL RE-REVIEW
        |
  REJECT/REWORK? ---> REMEDIATION -> TESTS -> FULL CI -> RE-REVIEW
        |
   APPROVE_GREAT
        v
VP ENGINEERING BRUTAL RE-REVIEW
        |
  REJECT/REWORK? ---> REMEDIATION -> TESTS -> FULL CI -> BOTH REVIEWS AGAIN
        |
   APPROVE_GREAT
        v
CREATE MACHINE-VALID P0 CLOSURE EVIDENCE
        |
        v
P0 RE-AUDIT + FINAL VALIDATOR/CI
        |
   FAIL? ----YES----> REOPEN OWNING FINDING
        |
        NO
        v
P0 ELIGIBLE FOR GOVERNED MERGE
```

## R1 — Field-bounded post-review finalization

### Invariant

After a candidate commit is frozen for review, later evidence/finalization commits may not alter program policy, future-phase definitions, acceptance criteria, ownership, maturity targets, dependencies, scope, non-goals, rollback text, or stop conditions without invalidating the review.

### Allowed semantic transition

For the reviewed phase only:

- `status`: `IN_PROGRESS|BLOCKED -> COMPLETE`
- `technical_verification`: `NOT_RUN|PARTIAL -> PASS`
- `outcome_verification`: `NOT_RUN|PENDING -> PASS|NOT_REQUIRED|PENDING` where the phase contract permits it

For the program pointer:

- `current_phase`: reviewed phase -> immediate next phase, except terminal P13
- immediate next phase `status`: `NOT_STARTED -> IN_PROGRESS`, except terminal P13
- `program_evidence_state` remains non-VERIFIED until final program closure

Every other program value must remain byte-semantically equivalent to the reviewed candidate. Any broader program modification requires a new candidate SHA and new reviews.

### Proof

- positive allowed-transition test
- future-phase mutation rejection
- maturity mutation rejection
- acceptance-criteria mutation rejection
- lane-policy mutation rejection

## R2 — Exact-candidate immutable evidence binding

### Invariant

A closure may not rely on unauthenticated free-form evidence strings.

Every repository evidence reference must contain:

- `path`
- `sha256`
- `bound_commit`
- `kind`

The validator must:

1. reject path traversal;
2. require the evidence file to exist;
3. recompute the file SHA-256;
4. require `bound_commit` to equal the reviewed candidate or an explicitly allowed evidence-finalization commit class;
5. reject mismatched hashes and candidate SHAs.

External CI identifiers may be recorded inside an immutable repository evidence receipt, but a bare workflow URL/run ID is not sufficient closure evidence.

## R3 — End-to-end phase closure tests

### Required positive fixture

Create a temporary Git repository that contains:

- canonical program state;
- candidate source commit;
- immutable evidence files;
- two schema-valid reviewer verdict files with distinct contexts and the same computed evidence hash;
- a phase closure file;
- an allowed final program transition.

Run the real program validator against that temporary repository and require `PASS`.

### Required adverse fixtures

- changed future-phase policy after review -> FAIL
- reviewer evidence hash spoof -> FAIL
- reviewer context spoof -> FAIL
- evidence file content changed after hash -> FAIL
- evidence `bound_commit` mismatch -> FAIL
- candidate not ancestor -> FAIL
- unapproved post-review file -> FAIL

## R4 — Whole-program final closure gate

### Invariant

`program_evidence_state=VERIFIED` is illegal unless a separate final program closure exists and validates.

The final closure must prove:

- all P0-P13 core phases complete;
- each phase has a valid closure artifact;
- every extension lane is COMPLETE or validly DEFERRED;
- final integrated APIVR: Audit, Plan, Implement, Audit Implementation, Verify, Re-Audit = PASS;
- final 20 Pass Protocol = 20 material improvements;
- final security/privacy/data review = PASS;
- final architecture review = PASS;
- final release/end-to-end review = PASS;
- rollback/containment summary = PASS;
- two independent final reviewer verdicts = `APPROVE_GREAT` on the same final evidence hash.

No collection of phase closures substitutes for this program-level closure.

## R5 — Evidence-bound extension-lane deferral

### Invariant

A lane cannot become `DEFERRED` as a bare status.

A deferred lane must contain a `deferral` object with:

- `reason`
- `decision_date`
- `decided_by`
- `evidence_refs`
- `revisit_trigger`

The validator rejects `DEFERRED` without all fields and verifies repository evidence references using the same immutable evidence contract.

## R6 — Outcome-state normalization

### Invariant

`COMPLETE + NOT_RUN` is always invalid.

Canonical outcome states:

- `NOT_RUN`: phase has not executed far enough to assess outcome
- `PENDING`: measurement horizon exists but is not mature
- `PASS`: required observable outcome met
- `NOT_REQUIRED`: phase is governance/contract-only and has a documented reason
- `FAIL`: observed outcome failed
- `BLOCKED`: outcome cannot currently be measured because of an external blocker

A COMPLETE phase may use only `PASS`, `NOT_REQUIRED`, or explicitly allowed `PENDING`. P12 and P13 require `PASS`.

## R7 — Lifecycle-policy single source of truth

### Invariant

Executable lifecycle policy lives in one canonical machine-readable policy artifact. Python derives phase order, lane order, maturity targets, FORENSIC phases, write-safety boundary, and final program-closure requirements from that artifact rather than hard-coded duplicate tables.

Canonical policy artifact:

`evaluation/remediation/autonomous-seo-expansion-policy.json`

The program JSON remains the mutable program state/plan. The JSON Schema remains structural validation. The Python validator consumes the canonical policy and verifies the program conforms to it.

## Required remediation evidence

Before re-review:

- exact new candidate SHA
- base..head changed-file list/diff
- focused tests for R1-R7
- program validator PASS
- full canonical GitHub CI PASS
- security/quality/release jobs PASS
- rollback certification PASS
- no temporary diagnostic workflow or bypass remains

## Re-review rules

The Senior ScrumMaster 3 and VP Engineering re-reviews must:

- evaluate the new frozen candidate, not the rejected candidate;
- receive the same evidence package;
- not use prior investment or implementation effort as evidence;
- identify at least three substantive objections even when approving;
- use `REJECT_BAD`, `REWORK_GOOD`, or `APPROVE_GREAT` only;
- treat one rejection/rework as blocking;
- trigger another remediation/CI/re-review loop on any material finding.

## Stop condition

P0 does not close and PR #37 does not merge until both fresh re-reviews return `APPROVE_GREAT` and the machine-valid P0 closure plus final P0 re-audit pass on the exact post-review evidence-finalization state.
