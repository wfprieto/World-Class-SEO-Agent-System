# Releasing

Public releases remain fail-closed. The August readiness/reviewer records are
historical BLOCKED evidence, not approval of today's main. A protected code merge,
a local PASS label, preparation, or a workflow dispatch is not final approval.
Run `python -B -m scripts.publication_cli status` for local configuration status;
it never grants publication authority. See [remaining evidence](PUBLICATION-BLOCKERS.md)
and the [protocol and data contract](adr/trusted-publication.md).

The manual workflows separate building from publication credentials. They require
the actual owner as both original and rerun actor, exact current protected main,
the selected canonical CI run's latest successful attempt and all fourteen unique jobs, including
all six Windows/Ubuntu Python 3.11/3.12/3.13 cells. Every job retains full history,
pinned actions, a trusted interpreter and adjacent isolated source proofs.

| Stage | Authority | Result |
| --- | --- | --- |
| Preparation `build` | Contents/actions read; no signing or publication write | Build once, clean-wheel smoke, SBOM, source manifest, checksums and detached subject |
| Preparation `attest` | Contents/actions read; narrowly scoped OIDC/attestation write | Verify current build handoff, attest all six files and wheel SBOM, preserve immutable candidate artifact |
| Release `authorize` | Read only | Authenticate C, E, bytes, executions and decisions; only `AUTHORIZED_NOT_FINAL` |
| Release `publish` | Contents write; no installers/build/signing | Recheck before writes, upload/read back approved bytes; only `PUBLISHED_UNCERTIFIED` |
| Release `complete` | Contents read; OIDC/attestation write | Observe real public bytes/tag and attest `COMPLETION_OBSERVED`, never self-approve its running workflow |
| Detached consumer | Read only; after producer success | Reauthenticate the completed exact run/attempt, receipt, current decisions and public bytes; only then emit `APPROVED` |

Freeze source C only after its exact-main CI succeeds. Start
`prepare-publication.yml` on main with that numeric `ci_run_id`. Record its final
`publication-candidate` artifact ID, archive digest, run/attempt and exact raw
`publication-subject.json` digest. The internal `publication-build` is not an
approved artifact. Preparation artifacts use one-day retention and subjects have
a 24-hour bound; an earlier actual provider expiry/deletion still blocks. Starting
a new preparation requires fresh evidence and decisions for its new tuple.

Use a separate data-only PR E based on C. E may add/modify only regular nonexecutable
JSON files under `publication-evidence/`; it is read by immutable Git object and
never checked out or executed. Changing main, E, prepared bytes, artifact IDs,
run attempts, or the decision tuple invalidates authorization. The subject does
not contain its own hash, E's commit, or its containing artifact ID. All twelve
final gates retain their canonical identities in `scripts/publication_policy.py`.
The two review gates require `APPROVE_GREAT`; the other ten require `PASS`.
Keep E open and unmerged, and keep main at C through detached completion. A later
main update or PR closure makes the receipt historical, not current authorization.

Before authorization, enroll real execution producers through a separately
protected and independently reviewed change to
`governance/publication-execution-authorities.json`. Its three empty allowlists
are an intentional denial, not test data to fill in. Pin real repository/owner/
actor IDs, executable workflow commit/ref and independence. Review producer code:
it must perform the permitted work and derive its seal from its own actual
outputs, not sign an evidence hash supplied by a caller. Runtime capability
promotion remains a separate deny-all policy and is not enabled by enrollment.

## Producer read access and real evidence

An enrolled producer outside this repository needs its own explicit read access:

| Execution gate | Fixed secret/environment name |
| --- | --- |
| `live_authorized_smokes` | `PUBLICATION_LIVE_READ_TOKEN` |
| `seven_archetype_benchmark` | `PUBLICATION_BENCHMARK_READ_TOKEN` |
| `external_reproduction` | `PUBLICATION_REPRODUCTION_READ_TOKEN` |

These are names, not configured credentials. After protected enrollment of a
reviewed real producer, its owner grants the required repository/Actions artifact/
attestation read access. The release maintainer configures the corresponding
secret through normal GitHub secret settings, using an approved secure handoff.
Do not paste values in chat, docs, logs or evidence. A missing external gate
credential blocks; the client does not fall back
to the primary publisher token or a local saved login. A same-primary-repository
producer may use the existing primary read access, but independent reproduction
must still satisfy its separate different-owner/actor/source requirements.

Each execution client is restricted to its selected repository's GET reads and
exact attestation verification, never arbitrary commands or writes. Each child
scrubs all other configured GitHub credential variables before receiving only the
selected token; helper-launched build/git children receive none. This subprocess
rule does not remove the pinned checkout action's required source-read access.
The publisher's contents-write
client stays on its own job token. Read secrets appear only in the three release
verification steps, not preparation, installers, build or signing steps. Access
does not authenticate a producer or waive any code, seal, identity or permission
check. The authoritative rules are in
[publication_credentials.py](../scripts/publication_credentials.py).

The evidence must include the complete controlled 7-by-15 benchmark, blinded raw
target/comparator outputs, adjudicated ground truth and unchanged thresholds;
bounded live/provider/account observations with real consent/budget/logs; and
independent clean installation of the exact staged wheel plus documented commands.
Unsafe secret exposure or unbounded paid calls from either benchmark system block
the run. Nine genuine capability closures are needed before publication; only
distribution remains pending until the consumer verifies actual public bytes.

Actual source argv/exit/result, concrete target and captured request/input bytes
must agree with explicit permission and redacted logs. Google report dates are
normal selectors, not freshness overrides. Render closure requires actual
install/health/page/screenshot on both Ubuntu and Windows, one job per OS with
correct chronology. Each event/request is authenticated against the real producer
attempt/job/platform/time, not self-labeled metadata. Current Bing remains
`BLOCKED_BY_CONTRACT`; its success cannot be manufactured with a typed packet.
IndexNow validation is not a submission, and HTTP202 is receipt/pending validation,
not indexing. Publish no credentials or PII: producers and owners must redact
before uploading real evidence, not rely on a hash or parser to anonymize it.

## Actual decisions and publication

Each canonical independent bot's latest GitHub PR review for E must remain
APPROVED and nondismissed, with a substantive `APPROVE_GREAT` structured decision.
A newer rejected/dismissed review is not permission to reuse an older approval.
Those decisions and the later, unedited
owner comment bind the same C/tree/E/digests/CI/preparation/artifact tuple. See the
exact decision schema in `scripts/publication_reviews.py`; display names, local
JSON verdicts, reactions or dispatch inputs are insufficient. Owner edit history
is checked through GitHub GraphQL, not just second-resolution REST timestamps.
The owner-selected [solo-maintainer policy](../governance/github-controls.json)
still requires exact-head repository-certification and resolved review threads.
It does not invent a second human approval or waive the independent bot release
reviews, genuine external reproduction or real owner publication consent.

After every real prerequisite passes, the owner may manually dispatch `release.yml`
on main with `prepare_run_id`, final `artifact_id`, `evidence_pr` and
`owner_comment_id`. This runbook does not authorize that action while evidence is
missing. The publisher never rebuilds or replaces bytes. A tag, draft or partial
upload already present stops the operation; there is no automatic partial resume.

After the exact release workflow finishes successfully, obtain its immutable
`publication-completion` artifact ID and run the read-only consumer:

```text
python -B -m scripts.publication_cli verify-completion --publication-run-id PUBLICATION_RUN_ID --artifact-id COMPLETION_ARTIFACT_ID
```

Replace the two descriptive parameters with actual numeric provider IDs; they are
not example approvals. The consumer authenticates the exact completed attempt,
all three jobs, six actual public asset IDs/bytes, tag and cryptographic provenance,
plus fresh authorization. It refuses deleted, expired, replaced or revoked proof.
Legacy `validate_phase6_readiness.py` still checks historical internal consistency,
but `--require-approved` can no longer authorize from local labels.

GitHub offers no atomic transaction joining reviewer revocation, main-ref changes
and release writes. Rechecks narrow that interval but do not eliminate it. Existing
repository administrators can act outside this workflow; its protocol is not a
replacement for GitHub access control. Do not claim platform release immutability
unless GitHub actually reports it. Otherwise the guarantees are no replacement by
this workflow and detectable identity/digest changes during later verification.

Certification uses a source-only checkout. Canonical Python workflows inherit the
exact top-level YAML setting `PYTHONDONTWRITEBYTECODE: '1'`; job, step, and container
overrides remain forbidden even when they repeat `'1'`. Other execution-altering
`PYTHON*` settings remain forbidden in canonical validation/release workflows.
The existing pinned historical rollback `PYTHONPATH` exception is not broadened.

Mandatory compilation still covers the complete checkout and still fails on
syntax errors. Only its output location changes:

```text
python -X "pycache_prefix=${{ runner.temp }}/wcseo-compile-cache" -m compileall -q .
```

The quoted runner-owned path supports spaces. The prefix applies only to this
compiler process; it is not a global `PYTHONPYCACHEPREFIX` setting. Compilation
must produce actual external `.pyc` artifacts and leave none in the checkout.
Ordinary imports and child Python processes without `-B` inherit the global
no-write policy. External compiler output is not source-authenticated evidence.

`-B` and `PYTHONDONTWRITEBYTECODE` suppress import-time cache writes, not reads of
existing caches; explicit compileall still writes its requested output.
`-X pycache_prefix` redirects that output to a parallel cache tree. See the
[official Python 3.13 command-line documentation](https://docs.python.org/3.13/using/cmdline.html)
(checked 2026-10-30). Isolated `-I`/`-E` proof processes ignore Python environment
settings; the no-write environment is not a substitute for their source checks.

Warm repository caches remain conservative, not generally portable: exact trusted
compiler byte comparison may reject genuine caches produced in another process,
interpreter, filename, or serialization context. Do not assume ordinary compileall
output will pass cache authentication. Candidate and restored-baseline proofs
continue checking matching tracked-source caches; headers/source hashes alone are
not authority, and cache bytes are never unmarshaled. Unknown, inconsistent,
orphan, and importable cache-directory impostors in certified repository roots,
including `security` and `contracts`, remain fail-closed. Use a clean source-only
checkout when cache authentication fails; the validator neither silently deletes
files nor grants cache exceptions. Recognized dependency caches outside certified
roots, such as ignored `.venv` files, are not source-certified; dependency/toolchain
trust remains separate.

Local source-only regression results do not replace the complete hosted matrix:
Windows and Ubuntu on Python 3.11, 3.12, and 3.13 must all certify the final head
before merge. Source-only CI does not approve a public release.

Autonomous rollback freshness is scoped to the recovery baseline in its receipt.
Only the three exact commits in `APPROVED_BOUNDARIES` may use the historical
claim-validation wrapper and its pinned review date. An unlisted full commit SHA
uses the original restored `validate-repository.ps1` with current-date freshness;
stale claims must still fail. The copied trusted helper's pure mode selector must
return exactly one recognized mode with a successful native exit before either
path runs. Classification does not replace the adjacent exact-tree/source proofs,
authorize a new date exception, certify current main, or approve P0 progression.
Historical substitution and environment overrides are restored/removed in
`finally`, including validation failures. The existing package-root bridge is
not a historical-date override.

Consumers can verify a downloaded artifact with:

```powershell
Get-FileHash .\world_class_seo_agent_system-*.whl -Algorithm SHA256
gh attestation verify .\world_class_seo_agent_system-*.whl -R wfprieto/World-Class-SEO-Agent-System
```

Those manual digest/provenance checks are diagnostics, not the full signer/source/
attempt/E/decision/completion authorization protocol. Use the detached consumer
for current final approval.

Rollback is release-specific: preserve the failed tag and evidence, identify the last verified release, publish a corrected version rather than replacing previously published bytes, and update the support declaration in `SECURITY.md`.
