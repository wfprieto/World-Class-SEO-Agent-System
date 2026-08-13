# Autonomous SEO Expansion P0 — Rollback and Containment Proof

Program: `autonomous-seo-expansion`  
Phase: `P0`  
Authority baseline: `c2252947a35606d70c01416975e38f668ce24c8b`  
Integration base at stabilization: `97bbd340d24e54c48d9b07e8d698d086758f403e`  
Integration branch: `agent/autonomous-seo-expansion-p0-integrated`

## Risk boundary

P0 adds governance, validation, review-trust, certification, test, and operator-evidence artifacts. It performs no SEO provider call, CMS write, Search Console mutation, Google Business Profile mutation, social publication, or autonomous production action.

## Authority baseline versus recovery baseline

The authority baseline records where P0 began. It remains immutable historical provenance.

The recovery baseline is different: it is the exact integration-target commit that is also the merge-base of the reviewed candidate and target branch. This distinction is required after unrelated work lands on `main`.

`scripts/rehearse_autonomous_seo_rollback.py` therefore:

1. resolves the authority baseline from the program;
2. resolves the integration target from `WCSEO_INTEGRATION_BASE_REF` (default `origin/main`);
3. computes the candidate/target merge-base;
4. requires the authority baseline to be an ancestor of that recovery point;
5. requires the recovery point to equal the current target commit, which rejects a candidate that is behind;
6. reverts only commits after that recovery point;
7. requires the resulting tree to equal the recovery-point tree exactly;
8. emits both authority and recovery baselines in the receipt;
9. restores HEAD to the recovery baseline for restored-baseline validation.

This prevents P0 rollback from removing independent `main` work such as the `97bbd34...` workflow-attestation update.

## Before merge

Containment is immediate: keep the integration PR unmerged or close it. `main` remains unchanged by P0.

## After merge

If P0 is later merged and a regression is discovered, use a bounded revert that removes only the P0 integration commits. Do not reset `main` to the historical authority baseline and do not revert unrelated commits that pre-date the P0 merge.

## Verification requirements

Rollback is accepted only when:

- the candidate is `0 behind` its integration target;
- authority-baseline ancestry is proven;
- candidate-to-recovery commit range is non-empty;
- post-revert tree equals the recovery-baseline tree;
- restored-baseline source-integrity validation passes;
- restored-baseline repository validation passes;
- no unrelated target-branch content is removed;
- the receipt records candidate, authority baseline, recovery baseline, target ref, commit count, and matching trees.

`tests/test_autonomous_seo_integration_rollback.py` provides real temporary-Git regression coverage for preserving post-authority `main` work and rejecting a candidate that is behind the target.

## Current state

`PENDING_CLEAN_INTEGRATION_CI`

The design and regression fixture are present. Final rollback PASS requires the stabilized exact candidate to execute successfully in GitHub CI against the current integration target.

This proof applies only to P0. P10-P13 require separate FORENSIC rollback proofs for any external write capability.
