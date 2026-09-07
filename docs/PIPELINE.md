# Pipeline Reference

Canonical reference for the nightshift-* pipeline stages, gates, and artifacts.

## Stage chain

```
nightshift-worktree.sh prepare TASK --project PATH [--base REF]  isolate before artifacts
/nightshift-product <REF>     ticket → spec, mirror to beads (canonical key = upstream ticket id, e.g. MVP-1)
/nightshift-adversarial <id>  claim verification via nightshift-code-fact-extractor
/implement <id>         build (with scope-freeze hook active)
/nightshift-review <id>       DRY/SOLID/ACID/CoC/BigO/LLM-trust + trend log
/nightshift-drift <id>        spec ↔ git-diff drift check
/nightshift-preflight <id>         pre-deploy checklist
/nightshift-deploy <id> [env] ship: tests → version → push → PR → poll CI → curl health check
```

`/nightshift-eng <REF>` orchestrates the whole chain with gates between stages and resume
across sessions via `.nightshift/<task-key>.md`. Existing `.claude/task-progress/<task-key>.md`
runs remain resumable in place.

## Ticket sources

`<REF>` formats accepted by `/nightshift-product` and `/nightshift-eng`:

- `gh:123` or `gh:owner/repo#123` — GitHub Issue
- `jira:KEY-123` — Jira (needs `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`)
- `monday:1234567890` — Monday item id (needs `MONDAY_TOKEN`)
- `notion:<page-id>` — Notion page (needs `NOTION_TOKEN`)
- `bd:bd-abc123` or bare `bd-abc123` — work directly off an existing bead

## Helper scripts

- `~/.claude/scripts/nightshift-ticket-source.sh <REF>` — adapter; emits normalized ticket JSON
- `~/.claude/scripts/nightshift-beads-mirror.sh` — stdin JSON → bd-id (idempotent via `ext:<ref>` label)
- `~/.claude/scripts/nightshift-scope-freeze.sh` — PreToolUse hook for Edit/Write that enforces the
  active-scope file written by nightshift-eng before `/implement`. No-op when no scope is active.
- `~/.claude/scripts/nightshift-spec-guardrail.sh` — PreToolUse hook for Edit/Write that blocks any
  `**/docs/<task-key>/SPEC.md` write missing a valid `## Sources` section or a filled
  `## Model Router` **Decision:** line.

## Hard rules

- **No gstack.** `/nightshift-*` never invokes `/ship`, `/land-and-deploy`, `/canary`,
  `/health`, `/review` (gstack), `/qa`, `/design-review`, `/autoplan`. Ideas were
  ported (drift detection, trend log, LLM trust boundary lens, scope-freeze, ship
  workflow shape) — implementations are local.
- **Beads is local-only.** The upstream ticket (Monday / Jira / GH / Notion) is the
  SSOT. Beads mirrors it via `--external-ref` for the local dev loop only.

## Canonical artifacts

All keyed by `<task-key>` (the upstream ticket id, e.g. `MVP-1`):

- `docs/<task-key>/SPEC.md` — spec
- `docs/<task-key>/.bd-id` — internal bead id (one line, no extension); used by stage
  skills for `bd note` / `bd close` calls
- `docs/<task-key>/REVIEW.md` — code review
- `docs/<task-key>/DRIFT.md` — drift report
- `docs/<task-key>/PREFLIGHT.md` — pre-deploy checklist
- `docs/<task-key>/DEPLOY.md` — deploy log
- `.nightshift/<task-key>.md` — pipeline tracker (resume state)
- `.nightshift/<task-key>-citations.jsonl` — adversarial verification log
- `.nightshift/.last-task-key` — written by nightshift-product, consumed by nightshift-eng
- `.nightshift/review-history.jsonl` — cross-task review trend log
- `.claude/task-progress/` — legacy task home, selected only to resume its existing task state

## Compaction strategy

`/nightshift-eng` emits a single-line marker on stdout each time the pipeline crosses a stage
boundary:

```
══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ <from> → <to> | compact-safe
```

At every `compact-safe` boundary, the prior stage's artifacts have been persisted to
disk (`SPEC.md`, `REVIEW.md`, `DRIFT.md`, `PREFLIGHT.md`, the tracker, the citation log)
and the next stage's skill reloads them on demand. Compacting at one of these boundaries
drops scratch reasoning without losing gate evidence — safe.

**One exception:** the preflight → deploy boundary emits

```
══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ preflight → deploy | DO NOT compact — deploy needs fresh diff
```

`/nightshift-deploy` re-reads the live `git diff` to produce the PR description and health-check
expectations. Compacting between preflight and deploy would drop the diff context the
engineer just confirmed in the preflight interview.

The marker is textual — no hook, no auto-`/compact` invocation. Harnesses that don't
recognize it ignore the line as noise; nightshift itself never calls `/compact`. To
make Claude Code's own auto-compaction less aggressive, set
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` in `~/.claude/settings.json` (see the README's
"Recommended Claude Code settings" section).

## Hooks (manual setup if not using `install.sh --with-hook`)

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write", "hooks": [
        { "type": "command", "command": "bash ~/.claude/scripts/nightshift-scope-freeze.sh" }
      ]},
      { "matcher": "Edit|Write", "hooks": [
        { "type": "command", "command": "bash ~/.claude/scripts/nightshift-spec-guardrail.sh" }
      ]}
    ]
  }
}
```

**`scope-freeze`** is a no-op until guarded activation publishes
`.nightshift/.active-scope-<task-key>` (or the resolved legacy state home) before implementation.
The hook enforces the union of `.active-scope-*` files; a bare `.active-scope` is ignored.
Matching retain-only finish retires ownership. A killed session retains scope and lease;
crash checks report them for reconciliation without unconditional thawing.

**`spec-guardrail`** fires only on Write/Edit whose `file_path` matches `**/docs/*/SPEC.md`.
For non-spec writes it approves silently. For spec writes it validates that the resulting
content has a `## Sources` section with at least one entry of the form
`` `path/to/file:LINE_START-LINE_END` ... commit: <sha> `` and a `## Model Router` section
with a non-bracket-placeholder `**Decision:**` line. Blocks the write with a detailed
reason if either rule fails.

## Isolation, ownership and completion

Eng resolves the stable upstream task key read-only and calls
`nightshift-worktree.sh prepare TASK --project PATH [--base REF]` before product artifacts,
sentinels, trackers or scopes. Batch performs the same gate independently for each ticket;
one failure does not stop other tickets. Every subsequent stage changes into the returned
worktree and resolves state there. Standalone implement prepares before spec-lock writes,
or validates the matching prepared receipt to continue its own in-progress product artifacts.

Branches are `nightshift/TASK`; default checkouts are sibling
`<repository-name>-worktrees/TASK`. Use `--root DIR` outside the caller checkout to override.
First preparation without `--base` uses current project HEAD. An explicit unmerged prerequisite
branch is passed verbatim with `--base`, recorded as dependency with its resolved SHA, and
never replaced by main. A clean resume without an explicit base keeps the recorded base.

Receipts in `<common-git-dir>/nightshift/worktrees/TASK.json` provide version, task,
repository identity, branch, absolute worktree, base_ref, base_sha, dependency and status.
Task locks serialize lifecycle operations. A changed base, nonancestral base, dirty reuse,
wrong repository/branch/path, malformed receipt or unowned resource fails closed with a
reconciliation diagnostic. Preserve partial resources and caller modifications.

One implementation may own a checkout at a time. Activate only through
`nightshift-scope-activate.sh TASK --project PATH --spec FILE`: it parses Files to Change,
adds matching task runtime artifacts, acquires the checkout-local lease at
`<state-dir>/.checkout-lease/owner`, and atomically publishes `.active-scope-TASK`.
Other-task leases/scopes identify their owner and block activation; malformed allowlists
cannot replace an existing scope. Separate worktrees have independent state and leases;
the scope hook retains union semantics.

On terminal completion call `nightshift-worktree.sh finish TASK --project PATH`. This
idempotently marks the receipt finished, retains worktree/branch/commits/dirty files, and
moves only matching lease/scope state into retained `.retired-TASK.*` metadata in the
checkout state home. Interrupted runs retain ownership for reconciliation. Do not add
unconditional thaw traps. Any manual removal of retained worktrees, branches or files
requires a separate explicit confirmation.

For two parallel tasks, prepare TASK-1, then prepare TASK-2 with
`--base nightshift/TASK-1`; enter each returned path separately. Each workflow owns its
scope and may finish independently. Run `bash evals/run-tests.sh` for offline regression
aggregation; `--root DIR` discovers fixture suites without recursively invoking the real
runner integration suite. CI runs this harness and shell lint for all pull-request bases.
