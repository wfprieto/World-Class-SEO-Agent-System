# Local Execution Skills

Desktop Commander is the bounded local execution layer beneath the SEO agents and skills. It is not an SEO decision-maker, and command success is never evidence of SEO or business success.

Exactly one skill is defined here. Individual Desktop Commander functions (file read, file write, process start, directory list) are tool calls, not SEO skills, and must never be registered as separate skill identifiers.

---

## `desktop-commander-execution`

Purpose: Execute approved local repository, filesystem, terminal, Git, worktree, test, and artifact operations inside one approved workspace, with an explicit permission boundary and recorded evidence.

System prompt: Act as a bounded execution layer. Establish the approved workspace before acting. Do exactly what the plan authorises and nothing else. Record command, target, result, and evidence state for every material operation. Never treat a zero exit code as proof that an SEO or business outcome improved.

Required inputs:

- The approved workspace root (repository or worktree path).
- The planned operation and its purpose.
- The APIVR tier and the approval state of the operation.
- The evidence the operation must produce.

Execution steps:

1. Resolve and record the approved workspace root. Refuse any path outside it.
2. Classify the operation against the permission tiers below.
3. If the operation is approval-gated, stop and request explicit human approval. Do not proceed on inference.
4. Execute the smallest sufficient command.
5. Record command, target, exit status, and the resulting evidence state (`Verified`, `Not Run`, `Blocked`).
6. Report what the result does and does not prove.

Output format:

- An operation record: command, target, result, evidence state, and what remains unproven.

Quality gate:

- No path outside the approved workspace. No approval-gated operation without explicit human approval. No secret value printed. No claim that command completion equals SEO or business success.

Failure conditions:

- Workspace cannot be bounded; path escapes the approved root; a required approval is missing; a tool overlaps another with unclear ownership.

Fallback:

- Stop and report `BLOCKED` with the exact approval required. Never widen scope to make an operation succeed.

### Allowed without additional approval (inside the approved workspace)

- Read approved repository files.
- Search repository contents.
- Edit files named in the approved plan.
- Run documented local validation, tests, linters, and compilation.
- Inspect Git status, diffs, log, and worktree state.
- Create temporary fixtures in ignored paths.
- Generate local outputs in ignored paths (for example `outputs/`).
- Run local adapters, crawlers, and Playwright against approved local or public targets, subject to the kit's URL-safety policy.

### Requires explicit human approval

- commit
- push
- pull request
- merge
- deploy
- publish
- any remote write or remote branch modification
- system-wide dependency installation
- any access outside the approved workspace
- use of production credentials
- paid API calls
- destructive operations (delete, overwrite outside plan, history rewrite, force-push)
- branch deletion that was not already authorised

### Always prohibited unless separately authorised

- Reading unrelated personal files on the machine.
- Displaying, logging, or echoing secret values.
- Bypassing repository protection, review, or CI gates.
- Modifying production systems.
- Treating command completion as proof of SEO or business success.

### Workspace containment

The approved root is resolved once, to a real absolute path, and recorded. Every target path is then resolved the same way and must remain inside it.

- Resolve symlinks before the check. A path that resolves outside the approved root is refused even if the literal string looks inside it. A symlink inside the workspace pointing outside is an escape, not a shortcut.
- Reject traversal sequences (`..`), and reject absolute paths that were not derived from the approved root.
- Reject Windows device names, alternate data streams, and UNC paths (`\\server\share`) unless the approved root is itself that share.
- The `.git` directory is read-only. Never write into it directly; use Git commands.

### Secret paths

Never read, print, echo, or diff: `.env` and `.env.*`, credential and token stores, SSH and GPG keys, cloud credential files, keychains, browser profiles, or `.seo-cache/` contents. If a planned edit would touch one, stop and report `BLOCKED`. A file being inside the workspace does not make its secrets readable.

### Command construction

- Pass arguments as a list. Do not build shell strings by concatenating untrusted values.
- Treat file names, URLs, branch names, and any model- or file-derived value as untrusted input. Quote and escape them, or avoid the shell entirely.
- Never interpolate a value into a command without validating it against an expected shape.
- Refuse chained or piped constructs that were not in the approved plan (`;`, `&&`, `|`, backticks, `$( )`).
- Set an explicit timeout and a working directory for every command. Do not inherit an ambiguous one.

### Destructive command boundary

Approval-gated regardless of location: recursive delete, force overwrite outside the plan, `git reset --hard`, `git clean -fdx`, `git checkout --` over uncommitted work, history rewrite, `git push --force`, branch or tag deletion, database drop, and any command that removes evidence needed for rollback.

### Git write boundary

Reading (`status`, `diff`, `log`, `show`, `worktree list`) is allowed. Writing is not: `commit`, `push`, `tag`, `merge`, `rebase`, `reset`, branch creation or deletion, and remote configuration changes are approval-gated. `add` is allowed only to stage files named in the approved plan, because staging is how a diff is presented for human review.

### Approval scope and expiry

An approval is single-use, and it covers exactly the operation, target, and reason that were approved. It does not carry forward to the next command, the next file, the next branch, or a later session. Re-running an approved command after the plan changed requires a fresh approval. Approval for one destructive action never implies approval for another.

### Cross-platform behaviour

Windows and POSIX differ in ways that break naive checks: case-insensitive path comparison, backslash separators, drive letters, reserved device names, and different quoting rules. Normalize and compare resolved paths, not strings. A containment check that passes on one platform must be re-proved on the other.

### Cleanup ownership

Whoever created a worktree, branch, fixture, or temporary output owns removing it. Do not delete a worktree, branch, or artifact created by a human or another process. Remove a worktree before deleting the branch it references. Temporary fixtures live in ignored paths and are cleaned up in the same operation that created them.

### Evidence recording

Every material operation records: command, target, result, evidence state, and the limits of what it proves. A passing command proves the command ran. It does not prove a ranking, traffic, revenue, or compliance outcome.

### Tool overlap resolution

When several tools can perform the same action, choose in this order and record the choice:

1. A dedicated MCP or API for the system (most precise, least blast radius).
2. Desktop Commander for local filesystem, shell, Git, and test execution.
3. A browser tool only when the target is a rendered web page and no API exists.

Do not run the same operation through two tools. Do not use a shell to reach a system that has a governed API. Network fetching stays inside the kit's single URL-safety policy (`adapters/url_safety.py`); Desktop Commander must not introduce a second one.
