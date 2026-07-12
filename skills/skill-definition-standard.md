# Skill Definition Standard

Every skill has one canonical procedure heading in `deep-skill-procedures.md`.

## Package eligibility

Add a record to `skills/package-registry.json` only when a skill has distinct inputs, outputs, commands or explicit advisory boundaries, failure behavior, references, and independent validation. The package record and its anchored section in `skills/packages/PRIORITY_SKILL_PACKAGES.md` are one self-contained capability unit.

Packages supplement grouped definitions. They do not replace the canonical procedure, command registry, evidence store, router, or scoring authority.

## Required package metadata

- `title`
- `execution_class`: `executable`, `advisory`, or `hybrid`
- `commands`
- `owners`
- `path` and `anchor`
- `canonical_procedure`
- `references`
- `quality_gate`
- `failure_states`

## Grouped definition minimum

Purpose, system prompt, required inputs, execution steps, output format, quality gate, failure conditions, and fallback.

## Sources of truth

- Inventory: `skills/skill-catalog.json`
- Package mapping: `skills/package-registry.json`
- Package document: `skills/packages/PRIORITY_SKILL_PACKAGES.md`
- Procedures: `skills/deep-skill-procedures.md`
- Generated index: `skills/SKILL_INDEX.md`
