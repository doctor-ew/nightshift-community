# Architecture

The design constraints that shaped nightshift, and the tradeoffs accepted along the way.

## Core constraints

1. **Source-agnostic ticketing.** A solo engineer works across multiple projects with
   different ticket systems (GH, Jira, Monday, Notion). The pipeline must not assume one.
2. **Local engineering ledger ≠ SSOT.** Beads is great for the local dev loop, but PMs
   live in Monday / Jira. Beads mirrors; never replaces.
3. **Adversarial verification before code.** LLM-written specs hallucinate. Every claim
   must be ground-truthed against the actual codebase before a single line is written.
4. **Scope drift is the silent killer.** `/implement` will happily edit anything in reach
   unless explicitly fenced.
5. **Resumable.** Solo engineers context-switch. The pipeline must restart cleanly from
   any stage, in a later session, on a different machine.
6. **No ceremony.** No 0-10 dashboards, no proactive nagging, no "boil the lake" preambles.

## Component diagram

```mermaid
graph TD
    subgraph "Ticket sources"
        GH[GitHub] -->|gh issue view| TS
        JIRA[Jira] -->|REST API| TS
        MON[Monday] -->|GraphQL| TS
        NOTION[Notion] -->|REST API| TS
        BD0[Beads] -->|bd show| TS
    end

    TS[nightshift-ticket-source.sh<br/>normalized JSON] --> BM[nightshift-beads-mirror.sh<br/>idempotent via ext:label]
    BM --> BD[(Beads DB<br/>local ledger)]
    BM -->|bd-id| PROD

    PROD[/nightshift-product/] --> SPEC[(SPEC.md)]
    SPEC --> ADV[/nightshift-adversarial/]
    ADV --> CITE[(citations.jsonl)]
    ADV -->|gate| IMPL[/implement/]

    SF[nightshift-scope-freeze.sh<br/>PreToolUse hook] -.blocks edits.-> IMPL
    SCOPE[(.active-scope-&lt;task-key&gt;)] -.read by.-> SF

    IMPL --> CODE[changed files]
    CODE --> REV[/nightshift-review/]
    REV --> RVMD[(REVIEW.md)]
    REV -->|gate| DRIFT[/nightshift-drift/]
    DRIFT --> DRMD[(DRIFT.md)]
    DRIFT -->|gate| PRE[/nightshift-preflight/]
    PRE --> PRMD[(PREFLIGHT.md)]
    PRE -->|gate| DEP[/nightshift-deploy/]
    DEP --> PR[(PR)]
    DEP --> HEALTH[curl health check]

    ENG[/nightshift-eng/<br/>orchestrator] -.chains.-> PROD
    ENG -.chains.-> ADV
    ENG -.chains.-> IMPL
    ENG -.chains.-> REV
    ENG -.chains.-> DRIFT
    ENG -.chains.-> PRE
    ENG -.chains.-> DEP
```

## Tradeoffs accepted

**No browser-based canary.** Gstack uses a browse daemon for post-deploy screenshot diffs.
Nightshift-pipeline uses a curl HTTP health check instead. Less coverage, ~zero infra to install.
If you need richer post-deploy verification, layer it as a separate step.

**No composite health score.** Trend tracking yes (per-lens severity counts in JSONL),
0-10 dashboard no. The ceremony cost outweighs the signal value for solo work.

**Heuristic AC coverage detection in nightshift-drift.** Searching the diff for AC keywords is
imperfect — false positives surface as WARN, not BLOCK. The alternative (asking the
engineer to tag every AC with a covering test name) was rejected as too much friction.

**Two-level id scheme: visible task key + internal bead id.** The task key is the
upstream ticket id (e.g. `MVP-1`) — what humans recognize and what shows up in
`docs/<task-key>/`. The bead id is internal, recorded in `docs/<task-key>/.bd-id`,
used only for `bd note` / `bd close` calls. The earlier design used the bead id
everywhere; that produced opaque folder names like `docs/orchestration-worker-3rg/`.
Trade-off accepted: a ticket renamed upstream needs a `mv docs/<old>/ docs/<new>/`
+ rerun (acceptable for solo work; rare in practice).

**Plugin and installer are both shipped.** The plugin manifest gives Claude Code direct
access to commands; the installer adds the scope-freeze hook (which plugins don't yet
ship). Some redundancy, but the alternative (forcing one or the other) is worse for
real-world setup.

## Why beads (not GitHub Issues)

GitHub Issues was the original implementation. It failed the source-agnostic constraint
the moment work moved to a project where GH wasn't the SSOT. Beads:

- Local — no API rate limits, no auth dance per-project
- Has `--external-ref` and labels — mirrors any source losslessly
- Has `bd query` with label filters — idempotent lookups by external id
- Solo-friendly — no team coordination layer to skip past

The local-only constraint matters: beads is part of the dev loop, not the project ledger.
PMs never see it. That separation is the feature.

## Why glob matching in python (not bash)

`nightshift-scope-freeze.sh` uses `python3` for glob matching because macOS bash 3.2 lacks `globstar`.
The hook is fast enough (single python invocation per Edit/Write) and the alternative
(requiring bash 4+ via brew) is fragile.

## File-counting decision tree (Model Router)

The spec's `## Model Router` section is required. Decision tree:

- ≥ 3 files OR ≥ 2 top-level modules → **Opus**
- Architecture or design decision → **Opus**
- Shared contract change (API, DTO, hook signature) → **Opus**
- Otherwise → **Sonnet**

The decision is enforced by the `spec-guardrail` hook (not shipped here; assumed to live
in your spec-writer skill). A bracket placeholder `[ ]` in the model router section will
be blocked.

## Shell portability: `printf '%s'`, not `echo`, for piped JSON

Command specs and scripts in this repo use `printf '%s' "$VAR" | jq ...` rather than
`echo "$VAR" | jq ...` whenever the captured value is JSON or contains backslash
sequences. Reason: on shells where `echo` interprets backslash escapes (POSIX `xpg_echo`,
dash sh, fish, and Bash tool invocations that route through them), an embedded `\n`
inside a JSON string value gets converted to a literal newline (U+000A) — which JSON
forbids inside string values — producing a `control characters from U+0000 through
U+001F must be escaped` parse error on otherwise-valid JSON.

`#!/usr/bin/env bash` scripts that set their own shebang are bash-safe (bash's builtin
`echo` doesn't interpret escapes by default), but command specs are executed inline by
the agent under whatever shell the harness uses — and that shell often does interpret.
The defensive rule: anywhere you capture JSON into a variable and re-pipe it, use
`printf '%s'`. This applies in both `.md` command specs and `.sh` scripts.

## Agent roles are runtime-neutral

`agents/*.md` carry no `model:` frontmatter. Model, provider, sandbox, and effort are resolved
per dispatch from `routing.json`, keyed on `(role, gear)`.

Why the indirection, given that Claude Code reads `model:` natively:

1. **Escalation needs an axis that isn't the file.** Separate role files that differ only in
   effort duplicate instructions. One prompt plus a gear key expresses the ladder without triplicating the body,
   and keeps the ladder's shape in one readable table instead of scattered across frontmatter.
2. **Escalation can change provider, not just model size.** When a role fails at gear N, "try
   harder" and "try a different model family" are different remedies. A routing table can express
   the second one; frontmatter cannot.
3. **Adversarial verification wants independence.** A model verifying claims in a spec it wrote
   is grading its own work. `adversarial.cross_provider` routes claim verification to a different
   provider than the spec author. This is the single highest-value reason the indirection exists.

Both target CLIs support headless dispatch with the properties this needs:
`claude -p --output-format json --agents <inline-json>` injects a role body at call time, so no
per-runtime install step is needed; `codex exec --output-schema <file>` enforces a role's JSON
return contract at the provider. Local models route through `codex exec --oss`, reusing Codex's
tool loop rather than hand-rolling one.

## Dispatch stays in bash

The dispatch layer is bash + jq, not Python or Node, even though both are installed here.

`jq` resolves to `/usr/bin/jq` — a system binary. `python3` and `node` resolve into
mise-managed installs, and a mise install that is garbage-collected takes its dependents with
it. That is not hypothetical: an MCP server on this machine is currently dead with
`ENOENT ... /mise/installs/node/25.6.1/bin/node` after the pinned node version went away. A
pipeline whose dispatcher cannot start is worse than one with weaker schema validation — and
`codex exec --output-schema` recovers most of that validation at the provider anyway.

The tradeoff accepted: JSON-schema checking on the Claude path is structural (jq assertions on
required keys and types) rather than full JSON Schema.

## What's intentionally not here

- Multi-stakeholder approval gates
- CI runner integration (uses `gh pr checks` — works on any GH repo)
- Specific deploy platform code beyond curl health check
- Any gstack code or skill invocations
- A telemetry layer
