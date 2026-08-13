# P0 Senior Engineering Remediation and Integration Graph

Program: `autonomous-seo-expansion`  
Original development PR: `#37`  
Authority baseline: `c2252947a35606d70c01416975e38f668ce24c8b`  
Current integration base: `97bbd340d24e54c48d9b07e8d698d086758f403e`  
APIVR tier: `COMPREHENSIVE`

## Historical review record

Earlier Senior ScrumMaster III and VP Engineering reviews returned `REWORK_GOOD` on older candidate SHAs. Those reviews remain evidence of defects found, but they are not approval for any reconstructed candidate.

Material findings remediated across the P0 development history include:

- field-bounded post-review finalization;
- exact-candidate immutable evidence;
- positive E2E phase closure and spoof/drift tests;
- whole-program final closure;
- evidence-bound deferred lanes;
- normalized outcome states;
- lifecycle-policy single authority;
- external reviewer provenance that cannot self-authenticate from repository JSON;
- repository/PR/run/evidence replay binding;
- fail-closed behavior without Git history;
- reviewer actor independence;
- correct autonomous-program rollback;
- cross-platform Git-blob/CRLF handling;
- non-vacuous review-authentication state;
- causal dependency on exact-head canonical validation.

## Stabilization trigger

After unrelated work advanced `main` to `97bbd34...`, the original P0 branch was `85 ahead / 1 behind`. Because review receipts, CI receipts, evidence hashes, and closure state are SHA-bound, preserving the old history would create unnecessary review and rollback ambiguity.

## Current execution graph

```text
FREEZE FEATURE EXPANSION
        |
        v
RESOLVE CURRENT MAIN FROM GITHUB
        |
        v
CREATE CLEAN INTEGRATION BRANCH FROM MAIN@97bbd34...
        |
        +--> SLICE 1: schemas + lifecycle policy
        +--> SLICE 2: lifecycle + closure validators
        +--> SLICE 3: reviewer trust + authentication
        +--> SLICE 4: CI + integration-safe rollback
        +--> SLICE 5: tests + operator evidence
        |
        v
REQUIRE 0 BEHIND / CURRENT MAIN IS EXACT MERGE-BASE
        |
        v
DRAFT CLEAN INTEGRATION PR
        |
        v
FULL CANONICAL MATRIX + QUALITY/SECURITY/RELEASE
        |
   FAIL? ----YES----> ROOT-CAUSE FIX -> NEW SHA -> FULL CI AGAIN
        |
        NO
        v
WCSEO-SPECIFIC CERTIFICATION
        |
   FAIL? ----YES----> ROOT-CAUSE FIX -> NEW SHA -> BOTH PIPELINES AGAIN
        |
        NO
        v
FREEZE EXACT REVIEW CANDIDATE + EVIDENCE PACKAGE
        |
        +--> CLAUDE / SENIOR SCRUMMASTER III INDEPENDENT REVIEW
        +--> CODEX / VP ENGINEERING INDEPENDENT REVIEW
        |
  ANY REWORK? ------> BUILDER REMEDIATION -> NEW SHA -> CI -> BOTH REVIEWS AGAIN
        |
   BOTH APPROVE_GREAT
        v
LEARNING RECORD + MACHINE-VALID P0 CLOSURE
        |
        v
FINAL EVIDENCE-ONLY CI / SOURCE-DRIFT PROOF
        |
        v
GOVERNED MERGE
        |
        v
DELETE OBSOLETE P0 BRANCHES
        |
        v
VERIFY MAIN IS SOLE SOURCE OF TRUTH
```

## Integration invariants

1. Current `main` is never rewritten for P0 stabilization.
2. The clean integration candidate must be `0 behind` before CI freeze, review freeze, and merge.
3. The authority baseline remains historical provenance; it is not used to erase unrelated later `main` work.
4. Rollback recovery baseline is the exact target commit/merge-base, and a behind candidate fails certification.
5. Old reviewer approvals, CI runs, candidate hashes, and closure evidence never authorize a reconstructed SHA.
6. Repository reviewer manifests are pointers/claims. Provider/GitHub-side authenticated evidence is the trust root.
7. A source change after review invalidates both reviews except explicitly bounded evidence-only finalization.
8. No P1+ feature work begins before P0 is integrated and `main` is again the single current source of truth.

## Final verdict rule

P0 is eligible for merge only when exact-head canonical CI, WCSEO certification, rollback proof, independent Senior ScrumMaster III review, independent VP Engineering review, Learning Agent record, closure validation, and final source-drift verification all pass. One material `REWORK_GOOD` or `REJECT_BAD` restarts the remediation loop.
