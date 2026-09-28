---
name: nightshift
description: Get Nightshift help, explain changes, consult architect/dev/PM/UX, create planning artifacts, or run a guarded, beads-backed engineering stage from nightshift in Codex or Codex driving a local Ollama model. Use for a nightshift ticket workflow, spec, adversarial verification, TDD implementation, review, drift, QA, preflight, deploy, or batch run.
---

# nightshift

Use this skill as the Codex entrypoint for the repository's `nightshift-*` workflow.
It deliberately reuses the canonical stage instructions instead of maintaining
a second, drifting set of prompts.

## Invocation

`$nightshift <ticket-ref>`

This is the factory entrypoint. For example:

```text
$nightshift gh:123
```

It runs the complete `eng` pipeline autonomously and leaves a durable tracker
and stage artifacts in the consumer repository. No additional stage-by-stage
call is required.

Independent operation form: `$nightshift ops <arguments>`. Read
`commands/nightshift-ops.md` from the source checkout (or its installed shared
command) and use the operation controller directly. Do not wrap an operation in
`eng` or set up a second model-directed pipeline. Assessment, authorization,
execution and restart follow the same CLI/dashboard contract.

Advanced form: `$nightshift <stage> <arguments>`

Advisory commands: `help`, `explain`, `architect`, `dev`, `pm`,
`ux-designer`, `architecture`, `ux`, and `bmad`. For these, read only the
corresponding `~/.nightshift/commands/nightshift-<command>.md` (or
`commands/nightshift-<command>.md` in a source checkout) and follow its scope.
Do not set factory mode, start engineering, or apply the factory failure policy.
Architecture and UX may write their specified planning documents; the others
are read-only. These conversations are optional and do not add pipeline gates.

Stages: `eng`, `product`, `adversarial`, `implement`, `review`, `drift`, `qa`,
`preflight`, `deploy`, `batch`, and `spec`. If the first token is not one of
those stage or advisory names, treat the entire input as an `eng` ticket reference.

The terminal launcher also accepts `nightshift batch <tickets-or-query>`, `--branch
auto|<name>|none`, `--push`, and `--pr`. Preserve those factory options when reading
the stage argument. `--branch auto` is the default: create or reuse an isolated
ticket branch/worktree. It must never use the repository default branch.

Branch-enabled factory runs need writable Git metadata to create refs and
worktrees. The launcher uses Codex's `danger-full-access` sandbox only for
those runs; use `--branch none` for a workspace-write-only run that cannot
create branches, commits, or pushes.

`--push` means that, after implementation, review, drift, and QA pass, commit
only the ticket's verified source changes and Nightshift artifacts and push that
ticket branch with an ordinary (never force) push. Do not push on a failure,
empty diff, or unresolved gate. `--pr` requires `--push`; it opens a pull
request but never merges it. Neither option authorizes a production deploy.

For batch runs, apply the selected branch/push policy independently to each
ticket. Batch completion is verification plus optional branch push/PR; do not
run the deploy stage unless the caller explicitly invokes a deploy stage and
passes the production confirmation gate.

Read `AGENTS.md` first, then read `~/.nightshift/commands/nightshift-<stage>.md`
(or `commands/nightshift-<stage>.md` in a source checkout) in full. Treat the
argument portion as that command's `ARGUMENTS` value, execute its steps, and
write its artifacts. If no stage is specified, use `eng`. For a factory run,
set `AUTONOMOUS=true` and `NIGHTSHIFT_FACTORY_MODE=true` for every stage and delegate
as needed; do not reduce the pipeline to a plan or a handoff.

When a command says to ask for a supervised approval, plan review, ticket
confirmation, version choice, branch creation, dirty-tree continuation, or
non-production merge, proceed autonomously using the safe/default choice. The
only confirmation points are the ones specified in `AGENTS.md`.

## Factory failure policy

An evidence gate failing is a repair signal, not a request for human approval.
For implementation, review, drift, QA, or CI failures, identify the smallest
in-scope repair, apply it, and rerun the affected gate. Use a maximum of three
repair attempts per gate and preserve evidence from every attempt in the task
tracker. After the limit, stop that ticket with a concrete failure receipt:
failed gate, commands run, relevant output, changed files, and the next
operator action. Continue later tickets in a batch.

Do not autonomously broaden the specification to make a gate pass. An ambiguous
or internally contradictory ticket/spec is a valid terminal failure receipt;
it is not an invitation to invent product behavior.

The command documents use the shared `~/.nightshift/scripts/nightshift-*.sh` runtime
home. Claude Code compatibility links remain under `~/.claude/scripts/` until 1.0.0,
but no canonical command depends on them. If this is a source-tree
run before installation, replace that prefix with this repository's `scripts/`
directory.

## Safety and autonomy

Follow the confirmation policy in `AGENTS.md`. Do not stop for non-destructive
calls or normal reversible workspace work. For permanent deletion/removal or a
production deploy, complete all safe preparation first and ask immediately
before the action executes.

`/nightshift-deploy` may run its preconditions and tests, but requires a fresh,
explicit confirmation for a production deployment. Development and staging
deploys proceed autonomously.

## Local models

The same skill works under the Codex OSS loop. Start it with, for example:

```bash
codex --oss --local-provider ollama -m <coding-model> -C <consumer-project>
```

Use a coding-capable local model; small general chat models are not reliable for
the multi-stage workflow. `routing.json` is the per-role dispatch table;
the skill itself is provider-independent.
