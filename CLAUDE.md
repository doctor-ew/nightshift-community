# nightshift — project notes for AI agents

This repo is the source for the `/nightshift-*` Claude Code skills. See `README.md` for the
full pipeline overview and `docs/PIPELINE.md` / `docs/ARCHITECTURE.md` for design
rationale.

`AGENTS.md` is the cross-runtime counterpart used by Codex and local models.
Keep its autonomy and destructive-action policy aligned with this file.

## How this repo tracks its own work

nightshift uses [`bd`](https://github.com/gastownhall/beads) to track its own dev
work (worktree support, batched extractor, etc.) in `.beads/`.

```bash
bd ready              # find available work
bd show <id>          # view issue details (e.g. bd show dp-q1s)
bd update <id> --claim  # claim atomically
bd close <id>         # close on ship
```

Issue prefix is `dp` (nightshift).

## Everything nightshift installs is `nightshift-` prefixed

`install.sh` refuses to install a command, script, or agent whose basename does not start with
`nightshift-` (exit 65). This is not style — `~/.claude/{commands,scripts,agents}` are flat namespaces
shared with every other installed plugin, so an unprefixed name clobbers whoever got there
first, and a symlinked unprefixed path lets the *other* plugin's sync write into this repo.
Keep shared namespaces isolated so another plugin cannot overwrite this runtime.

**nightshift is standalone.** It invokes no command, agent, or script it does not ship. If
you reach for `/spec`, `/preflight`, `/implement`, or any external agent from inside a nightshift-* flow,
stop — vendor it instead.

## Agent roles live in `agents/`

The `/nightshift-*` commands delegate to five roles: `nightshift-spec-writer`, `nightshift-code-fact-extractor`,
`nightshift-engineer`, `nightshift-architect`, `nightshift-run-all-tests`. Their prompts are in `agents/` and
install to `~/.claude/agents/`.

Two rules when editing them:

- **Never add a `model:` key to a role prompt.** Model, provider, sandbox, and effort belong in
  `routing.json` under `(role, gear)`. A `model:` key in the frontmatter silently wins over the
  routing table in Claude Code and makes the ladder a lie.
- **Keep them runtime-neutral.** No provider-specific tool names, no external plugin script paths, no
  language assumptions in the *process* (language-specific *examples* are fine). These prompts
  must read correctly whether Claude, Codex, or a local model is executing them.

## Optional tools go through the capability probe

`scripts/nightshift-capability.sh --has <tool>` is the only place that decides whether `bd`, `mex`,
`gh`, `jq`, Playwright, or a provider CLI is usable. Never probe inline with `command -v`.

Nothing on that list is a hard requirement. `bd` in particular is the local ledger, never the
SSOT — `/nightshift-product` degrades to running without a bead rather than failing (the single
exception is a `bd:*` ticket ref, which needs beads by definition). Code-graph (`mex`) steps in
the agent prompts are guarded the same way and no-op on the projects, currently most of them,
that have no graph.

## What this repo is opinionated about (and what it isn't)

nightshift *is* opinionated about how **consumer projects** should use beads — see
the README's "Hard rules":

- Beads is the **local engineering ledger**, never the SSOT
- Upstream ticket (Monday / Jira / GH / Notion) stays the source of truth
- Canonical task key is the upstream ticket id; the bead id is recorded in
  `docs/<task-key>/.bd-id` and used only for `bd note` / `bd close`
- No gstack — the `/nightshift-*` skills never invoke `/ship`, `/land-and-deploy`, `/canary`,
  `/health`, gstack `/review`, `/qa`, `/design-review`

nightshift is *not* opinionated about:

- **Pushing.** `git push` is always the engineer's call. No skill in this repo pushes
  autonomously; no agent contract in this repo should mandate it either.
- **Replacing other agent context.** This file supplements `~/.claude/CLAUDE.md` and
  the user's memory system — it doesn't override them.
- **TodoWrite / TaskCreate / MEMORY.md.** Use them when they fit. Beads is for tracked
  engineering work with an external-ref shape; ephemeral session state belongs in
  tasks, and cross-session knowledge belongs in memory.
