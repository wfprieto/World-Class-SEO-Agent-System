# Command and Evidence Contracts

`seoctl/command-registry.json` plus its approved overlay remain the source of command identity, path, handler, owner, skills, execution class, and network class. `seoctl.command_contracts` derives exactly one runtime contract for every effective command and rejects missing, stale, duplicate, or contradictory mappings.

Each command contract binds:

- one callable handler with exactly one family-level definition;
- `schemas/seoctl-command-input.schema.json` and `schemas/seoctl-command-output.schema.json`;
- parameterized executable behavior evidence in `tests/test_command_contracts.py`, which invokes every effective handler through controlled local arguments and validates its actual envelope and exit code;
- `DETERMINISTIC` evidence mode for commands with no network access and `LIVE_CAPABLE` for provider or live-capable commands;
- the bounded failure taxonomy in `seoctl/result_contract.py`, including exact status/state/exit mappings and complete `code`, `type`, `state`, and `message` metadata.

The executable sweep proves dispatch callability, schema conformance, malformed-return rejection, and controlled local success or failure behavior. It does not claim command-specific business correctness, live-provider verification, deployed behavior, or real credentials; those remain separate proof classes.

`runtime.finding_registry.FindingRegistry` reconciles each finding reference against the output evidence inventory. Its `evidence_state` is one of `VALID`, `MISSING`, `STALE`, `DUPLICATE`, or `CONTRADICTORY`; higher-risk states take precedence and are never silently converted to accepted evidence. An evidence item's identical `id` and `source` are aliases for that one item, while separate items sharing either key and repeated references remain duplicates. Non-valid evidence produces `EVIDENCE_REVIEW`.

Action conflicts use the finding's optional structured `action_polarity` contract, not an open-ended list of contradiction words. Opposite `ENABLE` and `DISABLE` polarities conflict only when their normalized `target` is identical; those findings become `CONTRADICTORY` and `CONFLICTED`. Different targets and matching polarities are negative controls. If multiple specialists provide distinct findings for the same scope and either omits the contract, compatibility cannot be proven, so the findings require `EVIDENCE_REVIEW` rather than being accepted. A malformed contract also fails closed to review. This deliberately bounded static contract does not claim to understand natural-language negation, synonyms, paraphrases, or implied actions; producers must provide `action_polarity` to obtain an automatic conflict determination.

Run the bounded checks with:

```text
python scripts/validate_command_contracts.py
python -m pytest tests/test_command_contracts.py tests/test_world_class_runtime.py
python -m ruff check seoctl/command_contracts.py seoctl/result_contract.py runtime/finding_registry.py tests/test_command_contracts.py
python -m mypy seoctl/command_contracts.py seoctl/result_contract.py runtime/finding_registry.py
```
