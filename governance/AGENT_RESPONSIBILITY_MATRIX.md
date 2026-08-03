# Agent Responsibility Matrix

The canonical machine-readable matrix is `agent-responsibility-matrix.json`. It keeps a
specialist only when the specialist has an explicit functional responsibility, a globally
exclusive evidence anchor in the effective capability registry, and an accountable artifact.

## Retention and overlap rule

An agent name or persona is not a capability. Each retained agent has exactly one accountable
`responsibility_id`, a real output-template binding, an effective execution class, named
contributors and consulted roles, and a directed handoff. Contributors do not become
accountable owners by participating.

Each agent-specific evaluation case repeats `expected_handoff_to`; the validator requires exact
equality with the matrix and kills substitution with another valid non-self agent. This is a
bounded declarative consistency check, not graph reachability, workflow execution, or semantic
proof that a handoff will occur.

The validator also compares effective skills, evidence, knowledge, and templates after the
product-proof overlay. Exact functional duplicates and near-clones at Jaccard similarity 0.80
or higher are rejected, including renamed personas with one decorative capability.

## Verification

Run `python scripts/validate_agent_differentiation.py` and
`python scripts/validate_agent_differentiation.py --mutations`. The fixed suite covers clone,
near-clone, owner swap, duplicate ownership, undeclared contributor, wrong template, execution
class mismatch, handoff substitution, shared evidence, missing contract, and missing/duplicate
evaluation cases.

These are bounded static repository controls. They do not claim semantic uniqueness beyond the
declared contracts, model compliance at runtime, or real-world effectiveness.
