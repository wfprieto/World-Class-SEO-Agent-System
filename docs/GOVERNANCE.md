# Governance

## Decision rights

- Maintainer: repository direction and release authorization
- CODEOWNERS: review ownership by subsystem
- Senior ScrumMaster 3: adversarial process and usefulness review
- VP Engineering: architecture, security, cost, packaging, rollback, and supportability review

One rejection blocks release approval. Reviewer verdicts are never averaged.

## Change rules

1. Preserve one authority per concept.
2. Add red tests before material implementation when practical.
3. Record security, cost, privacy, and rollback implications.
4. Keep optional providers removable.
5. Do not auto-merge self-improvement output.
6. Public superiority claims require independently reproducible benchmarks.

## Repository operations

The bounded operational procedures are in
[`REPOSITORY-OPERATIONS.md`](REPOSITORY-OPERATIONS.md). The machine-readable operations registry
is authoritative for control ownership, backup status, issue bindings, metrics, thresholds, and
rollback triggers. Until fresh GitHub evidence confirms a distinct eligible collaborator, backup
ownership and independent merge availability remain `OWNER_ACTION_REQUIRED`.

Every material change must name its operations control ID, accountable owner, evidence class,
verification result, and rollback trigger. Public intake must contain no credentials, private
URLs, client data, vulnerability details, or private conduct reports.

## Release gate

A release candidate needs green CI, clean installation, current references, complete comparative evidence, both reviewer approvals, checksums, SBOM, migration notes, and rollback instructions.
