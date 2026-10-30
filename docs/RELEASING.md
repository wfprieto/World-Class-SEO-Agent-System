# Releasing

Public releases are fail-closed. A maintainer may create and push an exact semantic tag only after `evaluation/comparative/final-release-readiness.json` records `APPROVED` and every required gate records `PASS` or `APPROVE_GREAT`.

Before tagging, run the repository certification workflow on the exact commit and confirm both independent reviewer verdicts, authorized live-site evidence, clean external reproduction, and current comparative evidence. Then verify version consistency:

```powershell
python scripts/validate_phase6_readiness.py
python scripts/validate_release_version.py
```

The tag-triggered release workflow repeats the fail-closed gates, builds and clean-installs the wheel, generates a CycloneDX SBOM and hashed release manifest, writes SHA-256 checksums, creates GitHub build and SBOM attestations, and publishes those assets with the GitHub release. A blocked readiness decision prevents publication.

Readiness retains all twelve canonical gate identities; absent, empty, unknown, or
partial gate maps cannot authorize publication. APPROVED also requires actual
candidate-bound final reviewer approvals, complete code/live/external verification
states, candidate-bound CI metadata, and passed benchmark execution evidence.
`verification_evidence` must contain `live_authorized_smokes` and
`external_reproduction`, each with `state: "PASS"`, the exact `candidate_commit`,
and nonempty `evidence_refs` using repository-file SHA-256 and bound-commit records.
Those files must exist unchanged at the approved candidate. Gate labels cannot
override contradictory files. The current BLOCKED decision remains truthful and
does not authorize publication.

Certification uses a source-only checkout. The four Python workflows inherit the
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

Consumers can verify a downloaded artifact with:

```powershell
Get-FileHash .\world_class_seo_agent_system-*.whl -Algorithm SHA256
gh attestation verify .\world_class_seo_agent_system-*.whl -R wfprieto/World-Class-SEO-Agent-System
```

Rollback is release-specific: preserve the failed tag and evidence, identify the last verified release, publish a corrected version rather than replacing immutable artifacts, and update the support declaration in `SECURITY.md`.
