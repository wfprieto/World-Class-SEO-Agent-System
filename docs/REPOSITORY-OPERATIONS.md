# Repository Operations

This runbook covers bounded repository operations. It does not certify a deployment,
provider outcome, ranking, traffic, adoption, or release publication. The machine-readable
registry in `governance/repository-operations.json` is authoritative for control IDs, owners,
issues, status, verification commands, blockers, and rollback triggers. This document supplies
the verify, fail, recover, escalate, and stop procedures for those exact seven controls.

Run verification from a clean checkout at the repository root. Preserve command output and the
exact commit SHA. A role records accountability; it does not prove that a second person exists.
Until GitHub confirms a distinct eligible collaborator, independent merge availability remains
`OWNER_ACTION_REQUIRED`.

## Operating rules

1. Stop on a failed required check; do not relabel it as unavailable or out of scope.
2. Keep source, automated, CI, provider, deployed, operational, and external-result evidence
   separate.
3. Record decisions, exceptions, and recovery evidence in the issue bound by the registry.
4. Never put credentials, tokens, private URLs, client data, vulnerability details, or private
   conduct reports in public issues, pull requests, logs, or fixtures.
5. Revert only the affected bounded change and preserve prior verified phases and evidence.

<a id="ops-architecture-quality-debt"></a>
## architecture-quality-debt

- **Owner:** Repository maintainer, with architecture and quality owners accountable for their
  respective debt inventories.
- **Verify:** Run `python scripts/validate_architecture_contract.py`,
  `python scripts/validate_architecture_exception_disposition.py`, and
  `python scripts/validate_quality_ratchets.py`. Compare exact counts and digests with issue #26.
- **Fail:** Fail on a new edge or fingerprint, raised ceiling, unowned or overdue exception,
  count/digest drift, or phase change without issue-backed acceptance criteria.
- **Recover:** Revert the unauthorized edge or ceiling. If immediate removal is unsafe, restore
  the last non-regressing disposition and keep issue #26 open with exact scope and verification.
- **Escalate:** Architecture owner decides boundary changes; quality owner owns ceilings; security
  owner reviews network-boundary exceptions.
- **Stop:** Do not delete a ratchet, broaden an allowlist, or repeatedly replan debt without exact
  scope, ownership, acceptance criteria, and evidence.

<a id="ops-repository-governance"></a>
## repository-governance

- **Owner:** Repository maintainer operating the explicitly approved solo-maintainer policy.
- **Verify:** Run `python scripts/validate_repository_governance.py`. Use only centralized provider
  authentication to confirm the required certification, thread resolution, squash-only merge,
  linear history, deletion protection, force-push protection, and issue #27 closure.
- **Fail:** Fail when any required automated or structural protection weakens, evidence is stale,
  or the contract claims an unavailable second human reviewer.
- **Recover:** Restore the exact versioned solo-maintainer GitHub-controls contract and reopen
  issue #27 before another merge.
- **Escalate:** The maintainer owns access and ruleset changes; independent engineering agents may
  review evidence but never impersonate GitHub human approvals.
- **Stop:** Never invent a collaborator, approval, or provider observation. Do not merge unless the
  exact-head `repository-certification` check passes and all review threads are resolved.

<a id="ops-network-provider-boundaries"></a>
## network-provider-boundaries

- **Owner:** Repository maintainer, with capability and evidence owners responsible for individual
  claims.
- **Verify:** Run `python scripts/validate_product_contract.py`,
  `python scripts/inventory_comparator.py`, schema/evidence validators, and focused runtime tests.
  Reconcile results with issue #28.
- **Fail:** Fail on invented capability, duplicate authority, unbound evidence, stale target
  inventory, maturity inflation, or a score changed without a separately reviewed package.
- **Recover:** Revert the unsupported claim or capability together with derived artifacts; retain
  the gap as open in issue #28 until executable evidence exists.
- **Escalate:** Capability owner resolves behavior; evidence owner resolves proof; independent
  reviewers approve methodology or score changes.
- **Stop:** Do not convert documentation, fixtures, deterministic rules, or static coherence into
  live execution, external truth, deployment, adoption, or SEO-effectiveness claims.

<a id="ops-documentation-knowledge-truth"></a>
## documentation-knowledge-truth

- **Owner:** Repository maintainer, with documentation, knowledge, dependency, and security owners
  accountable for their surfaces.
- **Verify:** Run `seoctl system doctor`, `python scripts/validate_reference_freshness.py`,
  dependency and generated-document validation, and `python scripts/validate_repository_governance.py`.
  Record maintenance evidence in issue #29.
- **Fail:** Fail on stale provenance, missing digest, generated/manual drift, mutable workflow
  dependency, unsupported count, disabled security service, or undeclared tool requirement.
- **Recover:** Restore canonical registries and pinned dependencies first, regenerate only derived
  artifacts, and revert incompatible examples with their schema changes.
- **Escalate:** Knowledge owner handles sources, documentation owner handles operator instructions,
  security owner handles dependency risk, and maintainer handles provider settings.
- **Stop:** Do not refresh a global date to hide a stale pack or treat a local pass as current
  provider, dependency-service, or external-source evidence.

<a id="ops-security-intake"></a>
## security-intake

- **Owner:** Repository maintainer. A monitored private conduct destination remains
  `OWNER_ACTION_REQUIRED`; issue #30 tracks the blocker.
- **Verify:** Run `python scripts/validate_repository_operations.py`. Provider verification must
  attest the destination separately before this control can pass.
- **Fail:** Treat a missing, public-only, unmonitored, inaccessible, or security-only destination
  as failure. The private vulnerability route does not complete conduct intake.
- **Recover:** Remove an invalid destination, mark the control blocked, preserve non-sensitive
  evidence, and reopen issue #30 until a valid channel is provisioned and attested.
- **Escalate:** The maintainer provisions the destination. Security reports continue through the
  private vulnerability route; public support continues through Discussions or the support form.
- **Stop:** Never request or publish identifying conduct details publicly. Do not publish a personal
  email without explicit owner authorization.

<a id="ops-certification-supply-chain"></a>
## certification-supply-chain

- **Owner:** Repository maintainer; functional owners own recovery steps for their components.
- **Verify:** Run `pwsh -File scripts/validate-repository.ps1`. Confirm every registry runbook path
  and anchor resolves and rehearse bounded rollback in a disposable checkout. Track gaps in issue #31.
- **Fail:** Fail on a missing anchor, destructive or ambiguous step, manual-memory dependency,
  incomplete commit range, absent recovery owner, or procedure that cannot restore last-good state.
- **Recover:** Revert the unsafe runbook change, restore the last verified procedure, and keep issue
  #31 open until an isolated rehearsal passes.
- **Escalate:** Functional owner resolves procedure details; quality owner validates the rehearsal;
  maintainer authorizes provider-affecting recovery.
- **Stop:** Do not rehearse destructive provider changes against production, erase issue history,
  remove a collaborator automatically, or run rollback from a dirty checkout.

<a id="ops-runtime-evidence-integrity"></a>
## runtime-evidence-integrity

- **Owner:** Repository maintainer, with quality and security owners accountable for certification
  gates.
- **Verify:** Run `python scripts/validate_repository_operations.py` and
  `powershell -ExecutionPolicy Bypass -File scripts/validate-repository.ps1`. Require exact-head
  repository certification, OS/Python matrix, dependency audit, security/quality, clean-wheel,
  source-integrity, provider-authentication, and rollback jobs. Track control drift in issue #32.
- **Fail:** Fail on a skipped required job, mutable action, source drift, stale provider evidence,
  unsafe network boundary, unverified wheel, or rollback receipt for another commit.
- **Recover:** Revert the bounded offending range, restore pinned workflows and transports,
  regenerate disposable evidence, and certify the restored tree before retrying.
- **Escalate:** Quality owner handles deterministic gates, security owner handles supply-chain and
  network findings, and maintainer authorizes provider recovery.
- **Stop:** Do not substitute local evidence for CI/provider evidence, a build for publication, or a
  retained artifact URL for permanent proof.

## Closure boundary

Review starts only after every applicable control is verified, failures have linked learning or an
explicit no-material-learning result, exact-head CI and rollback pass, and provider-dependent
controls have fresh authenticated evidence. Publication, deployment, adoption, and real-world SEO
outcomes remain separate decisions.
