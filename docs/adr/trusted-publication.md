# Trusted staged publication

Status: accepted design, implemented in source. Publication remains BLOCKED until
the actual external evidence and authorization pass. This ADR records the protocol;
it is not a release certificate or permission to run live operations.

## Context and decision

Build and attest a candidate once, approve those exact bytes against separate
evidence, publish without rebuilding, then verify completion from outside the
successful publisher run. A tag-dependent approval before tagging creates a cycle;
a local PASS document does not establish who executed or approved anything.

The operator sequence is in [RELEASING](../RELEASING.md); unmet real inputs are in
[PUBLICATION-BLOCKERS](../PUBLICATION-BLOCKERS.md). The source below is authoritative.

| Term | Exact meaning |
| --- | --- |
| C | Current protected `main` commit and its exact tree, with the selected canonical CI run's latest successful attempt |
| Prepared bundle | Six fixed files from one completed `build` then `attest` preparation attempt |
| Subject | Exact raw `publication-subject.json` bytes binding C/tree/version/tag, CI/preparation IDs/attempts/time and five payload hashes |
| E | Separate immutable data-only PR head descending from C; read as Git objects, never checked out or executed |
| Execution seal | Registered producer's authenticated result binding its real execution context, relevant E section and all transitive records |
| Completion | Detached observed receipt, then a separate read-only consumer's fresh verification after the whole producer run succeeds |

## Prepared bytes and the hash graph

[publication_subject.py](../../scripts/publication_subject.py) defines the exact
names and roles. For the candidate's source version, the six files are:

| File | Binding |
| --- | --- |
| `world_class_seo_agent_system-<version>-py3-none-any.whl` | Wheel bytes |
| `world_class_seo_agent_system-<version>.tar.gz` | Source distribution bytes |
| `sbom.cdx.json` | Prepared SBOM |
| `release-manifest.json` | Prepared source manifest |
| `SHA256SUMS` | SHA256 of the preceding four files only |
| `publication-subject.json` | Names/roles/byte counts/SHA256 of all five payloads, including SHA256SUMS |

The checksum file does not hash itself or the subject. The subject does not include
its own hash, E, or its containing archive's provider ID/digest. The provider ID and
archive SHA256, exact raw subject SHA256 and immutable E identity are added later
to the authorization tuple. This directed graph needs no self-SHA fixed point.

The final `publication-candidate` is authenticated by actual provider artifact ID,
run/attempt and archive digest, not by its display name. Strict ZIP verification
rejects extra/missing members, duplicates, links, unsafe paths and size violations.
All six files need real provenance attestations; the wheel also needs the SBOM
attestation. [publication_bundle.py](../../scripts/publication_bundle.py) invokes
actual cryptographic verification with exact signer workflow/source/ref/predicate
and hosted-runner policy, then checks verified subject/invocation data. Unverified
predicate JSON, a signed unrelated marker or CLI exit0 alone is insufficient.

## Stages and privileges

The manual [preparation workflow](../../.github/workflows/prepare-publication.yml)
has `build -> attest`. Build has contents/actions read and installs the locked
toolchain, builds once and checks the clean wheel. Attest has contents/actions read
plus OIDC/attestation write, verifies the exact current-attempt `publication-build`
handoff, and signs bytes without an installer/build step. Consumers wait for both
jobs and the whole exact preparation attempt to succeed.

The manual [publication workflow](../../.github/workflows/release.yml) has
`authorize -> publish -> complete`. Authorize is read-only. Only publish has
contents write; it has no candidate/dependency install, build or signing step.
Pinned trusted-interpreter setup remains required. Complete has contents read
and narrowly scoped OIDC/attestation write. Permissions are job-scoped, not
step-scoped. Every checkout retains full history/tags, pinned actions, no persisted
checkout credentials, trusted Python and adjacent isolated source-integrity proofs.
Both the original actor and rerun actor must be the actual owner, on exact current
main. No nonowner rerun, ancestor substitution or tree-equivalent SHA is accepted.

## Evidence and real producer enrollment

E may add/modify only regular nonexecutable JSON at the fixed
`publication-evidence/evidence.json` entry and content-addressed
`publication-evidence/records/<sha256>.json` paths. Deletions, other source changes,
unsafe modes/paths, extra/unused records and mismatched raw bytes fail. E stays an
open non-draft PR based on C through final completion. Merging E or advancing main
before completion changes the authorization; do not do either to bypass a blocker.
See [publication_git.py](../../scripts/publication_git.py).

The [execution registry](../../governance/publication-execution-authorities.json)
starts with three empty allowlists. This deliberately denies publication. Enroll
real producers through protected, independently reviewed source changes before
freezing C. Pin actual repository/owner/actor IDs, workflow and executable source
commit/ref. Review the code that performs the permitted operation and derives the
seal from its own actual outputs. Never enroll a service that merely signs a
caller-supplied digest. External reproduction must have a genuinely different
repository owner/actor/context and install the exact staged wheel outside source.
The runtime capability-promotion [issuer list](../../governance/capability-certification.json)
remains separate and deny-all; publication registration does not populate it.

The evidence includes the complete seven-archetype, fifteen-task benchmark with
pinned comparator, raw target/comparator results, blinding, ground truth and
unchanged thresholds; authorized bounded live/account results; independently
reproduced documented commands; and actual external community observations.
Empty/partial source results retain their limitations, not invented success claims.

Concrete argv, nonbool exit0, source-shaped envelopes and request captures must
agree with actual normalized properties/domains/queries/URLs, input bytes and
explicit owner scope/method/endpoint/redirect/request/spend/write limits. Captured
file paths are inert; the publisher never opens them. Every request has its own
time/identity and reconciled redacted provider/application logs. Render proof
includes real install/health/page/screenshot on both Ubuntu and Windows, same job
per OS, distinct jobs and `install <= health <= page/screenshot` chronology. Actual
latest-attempt hosted job metadata must authenticate those event times/platforms;
labels alone do not. The complete transitive seal covers these records and inputs.
Source/code review, cryptographic provenance and semantic checks are all required.
Hashes and signatures do not anonymize records or grant account/site access.
Producers and owners must omit credentials and PII before uploading evidence.

Current Bing is `BLOCKED_BY_CONTRACT`; the typed parser does not enable it. Bing
closure needs genuine preflight, URL validation and separately consented actual
submission with agreeing captured URL sets. HTTP202 means receipt/pending key
validation, not indexing or crawling. See the source
[evidence parser](../../scripts/publication_evidence.py),
[capability checks](../../scripts/publication_capability_checks.py) and
[prerequisite checks](../../scripts/publication_prerequisites.py).

## Access is not authority

The three gate-specific external read credentials are documented in
[RELEASING](../RELEASING.md). They grant transport access only, not trusted execution
or permission to publish. Missing external credentials block without using the
primary publisher token or a local saved login. Each external client is restricted
to its selected repository's reads and exact attestation verification. Publication
helper subprocesses scrub other GitHub credential variables; helper-launched
build/git processes receive no GitHub credentials. This is not a claim that the
pinned checkout action needs no read access. Secret names in source are not
provisioned secrets. Owners
configure approved access through normal secret settings, never chat or evidence.

## Decisions, clock and final approval

The latest review from EACH canonical bot in
[publication_policy.py](../../scripts/publication_policy.py) must remain GitHub
`APPROVED`, nondismissed and bound to exact E. Its structured decision is
`APPROVE_GREAT`, with provider-derived review context and substantive objections;
unresolved important findings block. A later actual owner comment must be unedited
and bind the same composite with `AUTHORIZE_PUBLICATION`. GraphQL edit history
must agree with REST; same-second timestamp equality alone is not proof. Use the
exact source contract in [publication_reviews.py](../../scripts/publication_reviews.py),
not a second handwritten JSON schema. The solo-maintainer policy does not invent
a second human approval or waive these independent release decisions.
The canonical bot roles are `claude[bot]` for Senior ScrumMaster 3 and
`chatgpt-codex-connector[bot]` for VP Engineering, with numeric IDs pinned in source.
A local agent review or human-authored bot-lookalike comment cannot substitute.

Prepared subjects and decisions expire under the canonical policy; event/CI/origin
TTL and clock skew are separately bounded. Real validation accumulates validity
intervals. After downloads, signature checks and readback, the actual UTC clock
must still fall in their intersection immediately before each mutation or final
certification. There is no `--as-of`, caller-selected clock or timeless approval.
The current policy bounds prepared subjects, release decisions and completion
receipts to 24 hours; CI/execution/evidence use their separate seven-day bound and
at most five minutes' future skew. Earlier provider deletion/expiry or release
authorization expiry still wins. Site/account consent windows bind the actual
request times; publication neither extends them nor retroactively grants access.
These windows are not permission to reuse an older attempt.
Provider outage/deletion/expiry, changed main/E/attempt/bytes, edited owner consent
or newer nonapproved review blocks instead of reusing an older approval.

All twelve gate identities remain unchanged. `scrummaster3_verdict` and
`vp_engineering_verdict` require `APPROVE_GREAT`; the other ten require `PASS`, as
defined by `required_gate_values()` in publication_policy.py. Only real public tag
and asset verification can close the distribution gates after publication.

The complete job emits only `COMPLETION_OBSERVED` and attests/uploads
`publication-completion.json`. It cannot approve its own still-running workflow.
Only the detached read-only consumer, after the exact three-job producer attempt
successfully completes, authenticates the receipt/artifact/attestation and
reauthenticates current decisions and all six public asset IDs/bytes/tag. Only then
does it emit `APPROVED`. A local JSON label, preparation, code merge or workflow
dispatch is never final authorization. Receipts are current-head/time bounded;
later main changes or revocation make a fresh verification fail, not a permanent
certificate. See [publication_completion.py](../../scripts/publication_completion.py).

## Failure, alternatives and reversal

Publication does not overwrite, delete, force or clobber tags/releases/assets and
does not automatically resume after partial writes. Preserve an interrupted tag,
draft, uploaded bytes and evidence; inspect actual provider state read-only. A
corrected version or separately reviewed recovery design is needed, not a blind
retry or deleting the destination. Source rollback uses a normal protected revert;
published-byte recovery preserves history rather than replacing old bytes.
A timeout or post-publication recheck failure can leave public bytes without an
APPROVED result. Inspect the real state rather than assuming failure rolled back
the write; do not delete or republish automatically.

Local approval labels, rebuilding after review, tag-before-approval cycles,
same-run completion self-approval and arbitrary digest signers were rejected.
GitHub has no atomic transaction spanning current main, reviewer revocation and
release writes. Final rechecks reduce that interval but cannot eliminate it or
prevent administrator actions outside this protocol. Do not claim provider-level
immutability unless the provider actually reports/enforces it. Revisit this design
through a protected source/contract review if those assumptions change; never
relax a gate as a recovery shortcut.

## Evidence state

Source defines the protocol and local regression verification checks its guards.
That is engineering evidence, not live execution, independent review, producer
enrollment or publication evidence. Missing real inputs stay BLOCKED. Historical
August records remain historical. Documentation/local verification does not prove
an actual main PR, public tag/release, native security-scan/EOS certificate or
completed publication. Record real run/artifact/decision identities when those actions are
actually earned; do not relabel old receipts or synthetic fixtures.
