# Skill Definition Standard

Every skill definition must include:

1. Skill name
2. Purpose
3. System prompt
4. Required inputs
5. Execution steps
6. Output format
7. Quality gate
8. Failure conditions and fallback behavior

## Required Format

```markdown
## `skill-name`

Purpose: What this skill does.

System prompt: How the invoking agent should behave while using this skill.

Required inputs:

- Input 1
- Input 2

Execution steps:

1. Step one.
2. Step two.
3. Step three.

Output format:

- Template or schema.

Quality gate:

- What must be true before output is accepted.

Failure conditions:

- What can block or lower confidence.

Fallback:

- What to do when required data is missing.
```

