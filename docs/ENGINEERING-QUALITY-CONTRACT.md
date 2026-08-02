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

The validator parses workflow YAML structurally, rejects duplicate mapping keys, and requires every checkout step to use an immutable SHA with an effective `fetch-depth: 0`. Coverage and risk validation are separate, exact, dedicated steps in the same job and in that order; conditions, custom shells, `continue-on-error`, multiline wrappers, masking operators, or extra commands invalidate the gate. Missing history, ambiguous YAML, or weakened CI wiring fails closed.
