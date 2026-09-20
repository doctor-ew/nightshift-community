---
name: agents
description: Always-loaded project anchor. Read this first. Contains project identity, non-negotiables, commands, and pointer to ROUTER.md for full context.
last_updated: "2026-09-20"
---

# nightshift

## What This Is
A source-agnostic engineering pipeline with shared runtime-neutral stages and a local beads ledger (`AGENTS.md`).

## Non-Negotiables
- Keep installed names prefixed `nightshift-`.
- Keep roles runtime-neutral; route through `routing.json`.
- Keep beads local; upstream tickets remain authoritative.
- Never invoke gstack in this workflow.
Source: `AGENTS.md`, Project conventions.

## Commands
- Test: `python3 tests/test-release-inputs.py` (`tests/test-release-inputs.py` (line 145)).
- Setup: `nightshift setup` (`scripts/nightshift-setup.py` (line 64)).
- Dev/lint/build: [TO DETERMINE]; setup brief tooling is unspecified.

## Code Graph
Use the smallest relevant structured resolver. For Inbox or Relay mutations, resolve only the intended action with `mex inbox contract --action <command-id> --json` or `mex relay contract --action <command-id> --json`; use `mex capabilities --json` only for broader capability discovery. If the user explicitly asks to create, save, or draft a checkout-local Inbox or Relay draft, preview and apply that exact draft without asking for redundant confirmation. Deleting a local draft, or publishing, approving, rejecting, withdrawing, marking stale, repairing, taking or acknowledging, or closing, requires fresh explicit confirmation after semantic preview. Treat Git commit, push, and pull as separate actions requiring their own authorization.

The repo is indexed into `.mex/graph.db`. Use it to avoid re-reading code you already have — it is one tool alongside Grep/Glob, not a replacement for them.
- If you know the symbol name, go straight to it: `mex graph query <who-calls|what-calls|where-defined> <symbol>` and `mex graph get <id>` are exact and cheap. This is the strongest part of the graph. Give it exact names — an approximate name can return a confident wrong match.
- Exploring an unfamiliar task? `mex graph scope "<task>"` returns bounded, source-backed JSONL context plus trustworthy execution flows. Scope matches on words, not meaning, so treat it as starting evidence rather than a complete answer.
- Treat source returned by the graph as ALREADY READ; do not re-open those files.
- Read the summary status and evidence. `status: "ok"` remains usable when `truncated: true`; only optional evidence was omitted. For `partial` or `degraded`, narrow the task or follow `suggestedNextCommands`.
- Use `mex graph get <id> --detail source` only when source is missing, you need exact expansion, or a partial/degraded summary suggests it. Do not expand nodes by quota.
- If the evidence is insufficient or the task wording does not match the code, use Grep/Glob instead. Do not re-run `scope` with reworded phrasing more than once.
- Before editing a symbol, run `mex impact <symbol|file>` to see affected callers and scaffold memory.
- During `mex sync`, adjudicate any AMBIGUOUS grounding; after repairs, ensure the refreshed grounding is re-emitted.

## Scaffold Growth
After meaningful work, run GROW:
- Ground: what changed in reality?
- Record: update `ROUTER.md` and relevant `context/` files
- Orient: create or update a `patterns/` runbook if this can recur
- Write: bump `last_updated` on changed scaffold files and run `mex log` when rationale matters

The scaffold grows from real work, not just setup. See the GROW step in `ROUTER.md` for details.

## Navigation
At the start of every session, read `ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.

<!-- mex-agent:skills:start -->
## MEX context policy
- When MEX context materially influences an answer or implementation, include one concise acknowledgement: `MEX context used: <specific records/files/entities consulted>.`
- Do not claim an author, date, or historical event unless the retrieved data actually provides it.
- After a MEX write, say exactly what changed and its sharing boundary: a local draft is checkout-only and nothing is shared; a canonical artifact is written to the working tree and requires commit/push to share.
- Skill activation is not approval for canonical actions.
<!-- mex-agent:skills:end -->
