# Publication evidence and remaining blockers

Source cleanup and protected-main certification are separate from permission to
publish. No tag or public release is authorized by this document. All twelve final
release gate identities and existing protection/coverage/source-integrity rules
remain mandatory. The canonical August readiness and final-review files are
historical BLOCKED evidence; do not relabel them as a fresh evaluation.

## Evidence that still has to be earned

| Requirement | Needed proof | Responsible role |
| --- | --- | --- |
| Exact candidate code and dependencies | Complete Windows/Ubuntu Python 3.11/3.12/3.13 CI, aggregate repository-certification and fresh locked audits for the exact source | Engineering/CI |
| Authorized live capabilities | Real bounded observations within specific owner/provider scope; account access, budget and freshness where applicable | Maintainer and authorized operator |
| Seven-archetype comparison | Seven controlled archetypes, all fifteen tasks, pinned comparator, blinded outputs, ground truth, raw-to-score traceability and unchanged thresholds | Benchmark operator and independent evaluator |
| Final reviews | Genuine independent ScrumMaster3 and VP Engineering findings/verdicts bound to the same immutable candidate and evidence package | Independent engineering reviewers |
| External reproduction | Independent clean install and commands/results with source/artifact/environment identities; builder-local tests are insufficient | Independent reproducer |
| Tag and public bytes | Actual immutable semantic tag resolving to the authorized source, published wheel/sdist/SBOM/manifest/checksums and verified build/SBOM attestations | Release maintainer, only after publication authorization exists |

The owner supplied https://mlmas.com/ for a basic public-page smoke on
2026-10-30. The permitted scope is at most twenty total public GET requests,
including redirects, on mlmas.com/www.mlmas.com only, with no logins, paid
services, submissions, site changes or offsite resource fetching. This grant is
for this bounded validation run, not continuing monitoring or API/account access.
It cannot establish all seven archetypes, Google account integrations, rendered
browser behavior, independent reproduction or final release approval. A basic
fetch/parser receipt must retain its exact tested source identity; rerun the
affected check if that implementation changes.

## Sequencing and authority blocker

Current publication requires all twelve final gates before tag/build/publication,
including the two gates that can only become true after actual tag/publication.
It also stores candidate identifiers in files that cannot contain their own
containing commit SHA without a cryptographic fixed point. Merely accepting an
ancestor, a new approval label, or local file hashes does not establish authority.

A future publication implementation needs a separately challenged, executable
contract selecting all of the following before changing the guard:

- Frozen source commit/tree, exact version/planned tag, evidence-package digest
  and immutable built-artifact digests.
- A real trusted authority and authentication verifier, with authenticated
  storage/retrieval and freshness/revocation behavior. A local JSON status or
  reviewer display name is not authentication.
- Verification of actual successful candidate-bound CI, all six matrix cells,
  aggregate certification, genuine reviews/benchmark/live/external evidence.
- Narrow maintainer authorization to publish only those previously verified
  bytes; retrieve them unchanged rather than rebuild after approval.
- Actual tag/publication receipts checked against the frozen source and bytes.
  Final APPROVED remains impossible until all twelve completion gates pass.
- Negative tests for wrong source/repository/run, missing/duplicate/failed cells,
  stale or forged review/benchmark/reproduction evidence, tampering, artifact/tag
  substitution and prepublication authorization mistaken for final completion.

The current task does not invent this trust infrastructure, self-approve missing
evidence, or publish to break the cycle. Until that design and its required real
evidence are independently verified, publication remains BLOCKED. Internal
readiness consistency passing means only that a truthful blocked record is
consistent; it is not proof of readiness to release.
