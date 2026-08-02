# Engineering Quality Contract

This contract prevents maintainability debt from increasing while permitting bounded improvement of legacy code. It governs first-party Python under `runtime`, `adapters`, `integrations`, `seoctl`, and `scripts`.

## New-code defaults

- Files: at most 400 physical lines and aggregate AST complexity 180.
- Functions: at most 75 lines and deterministic AST branch complexity 15.
- Every non-method receiver parameter and every return value is annotated.
- New Ruff findings under `E4,E7,E9,F,I,B,UP,C4,SIM,C90` are prohibited.
- New cross-layer dependencies and direct network-capable modules are prohibited unless the architecture contract names an exact, accountable exception.

Legacy exceptions are frozen at their measured ceiling in `governance/code-quality-ratchet.json`. Each exception has an owner, rationale, and removal phase. Increasing a ceiling, adding an unknown path, deleting an annotation, increasing a grandfathered function, or adding a new lint fingerprint fails certification. Reductions are expected; the baseline must be tightened in the same bounded change so debt cannot rebound.

## Coverage

Repository branch coverage cannot fall below 78 percent. Critical files also have individual floors in the machine contract and `pyproject.toml`; a missing critical file is a failure. Coverage floors are regression controls, not assertions of operational sufficiency or real-world effectiveness.

## Typed runtime boundary

`runtime.adapter_contracts` is the canonical adapter port. Its explicit status vocabulary separates success, partial, missing, invalid, and blocking outcomes. The dispatcher rejects unknown statuses before evidence calculation, treats every required non-success as blocked, invalid, or missing, preserves request order and completed sibling evidence, propagates cancellation, and converts malformed optional output into an isolated failure. Compatibility imports preserve existing callers without defining a second class.

## Change procedure

1. Run both contract validators before tests.
2. Add a failing mutation for each new rule or exception class.
3. Tighten baselines whenever debt is removed. `--write-baseline` is reduction-only and requires `--approve-tightening` with the SHA-256 printed by a rejected unapproved write; it refuses new exceptions, raised ceilings, new Ruff fingerprints, or lowered coverage floors.
4. Run focused boundary tests, full mypy, the complete suite, branch coverage, risk coverage, security mutations, clean-wheel checks, and cross-platform CI.
5. Do not describe a green ratchet as proof of deployment, release maturity, provider operation, or SEO effectiveness.

The validator parses both validation and release workflow YAML structurally, rejects duplicate mapping keys, and recognizes checkout identity case-insensitively while requiring its canonical lowercase spelling, immutable action SHA, effective `fetch-depth: 0`, `persist-credentials: false`, and no settings beyond the canonical source-integrity set. Validation checkouts use the event-aware candidate expression: the pull-request head commit instead of GitHub's synthetic merge commit, and `github.sha` for push or manual events. Tag releases explicitly use the immutable event commit in `github.sha`. Repository, path, branch, tag, or other checkout-source overrides fail closed. Coverage and risk validation are separate, exact, dedicated steps in the same job and in that order. Step conditions, custom shells, `continue-on-error`, multiline wrappers, masking operators, extra commands, job conditions, inherited workflow/job shell and working-directory defaults, or inherited environment variables that can alter Python, pytest, coverage, imports, executable discovery, or command interpretation invalidate the gate. Unrelated job metadata remains permitted. Missing history, ambiguous YAML, or weakened CI wiring fails closed.

Every repository-dependent command and release attestation must immediately follow the canonical observational source-integrity gate. The gate independently hashes tracked worktree content, compares the full staged index and file modes with `HEAD`, proves `HEAD` equals the event SHA, and rejects untracked import-shadowing source. This remains effective when Git marks a file `assume-unchanged`. Workflow command-channel writes through `GITHUB_ENV` or `GITHUB_PATH`, inherited execution controls, containers, services, self-hosted runners, and runner matrices outside the exact GitHub-hosted allowlist fail structurally. Rollback jobs prove the candidate immediately before their intentional tree replacement and then use their separate exact-baseline tree proof.

The certification job IDs, complete matrix objects, runner assignments, immutable action sequences, checkout/setup bootstrap order, and action pins are exact contracts; deleting checkout does not remove a named job from enforcement. Source proofs execute with an absolute interpreter path captured before dependency installation and with Python isolation flags. Dangerous job or step environments and direct or constructed writes to GitHub's persisted environment and path command channels fail closed. Rollback jobs enter baseline mode only through the exact canonical rollback operation, then require a fresh exact-tree and worktree proof immediately before every baseline install, validation, test, receipt-sealing, and artifact boundary.
