# nightshift

For the engineer pilot and Hack-her-thon, start with the
[pilot quickstart](docs/PILOT-QUICKSTART.md). Use main; local-model upgrades and
ACP remain experimental. Fresh-machine, independently reviewed end-to-end
validation is still required before claiming beginner readiness.

A source-agnostic, beads-backed engineering pipeline for Codex, Claude Code, and
Codex driving local models.
Drop a ticket reference (gh / jira / monday / notion / bd), get a guarded path from
spec through ship.

```
/nightshift-eng <REF>
   ├─ nightshift-product       ticket → spec, mirror to beads
   ├─ nightshift-adversarial   claim verification + SPEC-DIGEST / trimmed citations
   ├─ nightshift-implement     TDD build: spec-lock → RED (firewall) → red-lock → GREEN
   ├─ nightshift-review        TDD integrity gate, then DRY/SOLID/ACID/CoC/BigO/LLM-trust + trend log
   ├─ nightshift-drift         spec ↔ git-diff drift check
   ├─ nightshift-qa            behavioral QA — full Playwright suite (no-op when absent)
   ├─ /nightshift-preflight         pre-deploy checklist
   └─ nightshift-deploy        ship (+ @smoke Playwright against the live URL)

/nightshift-batch <keys|query>  triage → run each ticket through /nightshift-eng autonomously → retro
```

Each stage is a standalone slash command and gates the next. The orchestrator (`/nightshift-eng`)
is resumable across sessions via `.nightshift/<task-key>.md` (with a compatibility reader for
existing `.claude/task-progress/<task-key>.md` runs), and runs a
context-budget check on entry to each stage so long runs bail to a `--from` resume hint
instead of hitting a context wall.

Use `$nightshift`, `nightshift`, and `/nightshift-*`. Retired compatibility
entrypoints are no longer installed. Historical run evidence remains readable.

---

## Why

Spec-driven workflows fall apart for two reasons: ticket sources that don't match the spec
generator, and gradual scope creep during implementation. nightshift addresses both.

- **One pipeline, any ticket source.** Adapter for GitHub, Jira, Monday, Notion, and beads.
  No project owns the canonical key — beads does, locally.
- **Beads is local-only.** Upstream ticket (Monday / Jira / GH) stays the SSOT. Beads
  mirrors it via `--external-ref` for the local dev loop. The upstream ticket id
  (e.g., `MVP-1`) is the visible task key; the bead id is recorded internally in
  `docs/<task-key>/.bd-id` and used only for `bd note` / `bd close` calls.
- **Adversarial claim verification.** Every spec claim is checked against the codebase
  before a line of code is written. No fabricated facts reach production. The
  `spec-guardrail` PreToolUse hook also blocks any SPEC.md write that lacks a verified
  `## Sources` section or a filled `## Model Router` decision.
- **Scope-freeze during `nightshift-implement`.** Guarded task scope activation acquires a
  checkout-local implementation lease. Matching retain-only finish retires it; interrupted
  runs preserve ownership for reconciliation.
- **Managed worktree isolation.** `nightshift-worktree.sh` prepares a separate checkout
  before any product or state writes. Caller edits remain intact.
- **Stop hook.** With `--with-hook`, a Stop hook blocks session close while a pipeline stage is
  still `⏳ in-progress`, so a half-finished stage isn't silently abandoned (fail-open on retry).
- **Tamper-evident TDD.** `nightshift-implement` seals `SPEC.md` and the failing RED-phase tests
  under a `nightshift-bot@local` git identity; `nightshift-review` fails if any non-bot commit touched a
  locked path after sealing. "Tests went green" becomes provable, not assertable. The GREEN
  agent runs behind a firewall that hides the test source, so it designs to the spec rather
  than to the assertions. Tests that pass on unpatched code exit as already-fixed-upstream.
- **Token-aware review.** `nightshift-spec-digest` extracts only the acceptance criteria + guardrails
  into `SPEC-DIGEST.md`; the review lenses read that, not the full Solution/TRD — cheaper, and
  unanchored by the author's rationale.
- **Autonomous batch.** `/nightshift-batch` triages a set of tickets (keyword gates that exclude
  design-heavy / security-sensitive / integration-coupled work) and runs each survivor through
  the whole pipeline unattended, writing per-ticket outcomes and an aggregate retro. Resumable
  from its state file.
- **Trend tracking.** `nightshift-review` writes JSONL deltas vs the previous run. Regression
  visible without a 0-10 dashboard.
- **No gstack.** Ideas were ported (drift detection, scope-freeze, LLM trust boundary lens).
  Implementations are local — nightshift never invokes a gstack-namespaced skill.

---

## Install

### Option A — Codex first (recommended)

```bash
git clone https://github.com/doctor-ew/nightshift-community.git
cd nightshift-community
./install.sh --runtime codex --with-hook
```

This installs the native `$nightshift` Codex skill in `~/.codex/skills/` and
the shared runtime in `~/.nightshift/`. Start Codex from a consumer repository
and make one call:

```text
$nightshift gh:12
```

That is the factory entrypoint: it runs `nightshift-eng` end-to-end in autonomous
mode, uses bounded in-scope repair loops for ordinary gate failures, and leaves
a durable receipt if it cannot finish. Use `$nightshift <stage> <args>` only
to start or resume an individual stage deliberately.

For a literal terminal one-call entrypoint, use the agent-agnostic launcher:

```bash
nightshift gh:12
```

Factory branch hygiene is enabled by default. To commit and push a fully
verified ticket branch (without merging or deploying), opt in explicitly:

```bash
nightshift gh:12 --branch auto --push
nightshift gh:12 --branch auto --push --pr
```

The launcher defaults to your ChatGPT subscription authentication and refuses to
run when Codex is logged in with an API key. This prevents an inherited
`OPENAI_API_KEY` from silently billing API usage. Paid API use requires an explicit
`--auth api` on each launcher invocation. A previously saved API preference is
ignored with a warning; it cannot silently authorize a new paid run. Codex
subscription runs also pin the login method to ChatGPT and provider to OpenAI.

Run independent tickets in sequence with the same policy:

Select Claude Code with `--provider claude`; pass `--model sonnet` or a model ID
to choose its model. This requires an installed, authenticated Claude Code CLI.
Batch `--resume` uses the same Nightshift state file with either provider.
The default subscription mode removes `ANTHROPIC_API_KEY` and
`ANTHROPIC_AUTH_TOKEN` for both runtimes and requires Claude's authentication
status to report a first-party claude.ai login before starting its worker.
Use `--auth api` to retain billing credentials for that run. No capacity or
quota error triggers an automatic switch to API billing.

This is a launcher authentication guard, not an account-wide spending firewall:
direct slash-command sessions, independently launched reviewers, stored tool
credentials, and arbitrary worker tool calls still need the shared gateway.
Subscription extra-usage purchases are controlled by the provider account, not
by this API-mode guard. Model tiers, dollar budgets, and remote hosting are not
configured by this change.

```bash
nightshift batch "MVP-1,MVP-2" --push
nightshift batch --resume batch-YYYYMMDD-HHMM.json --push
```

## Versioned branch sync

`VERSION` stores the semantic release version. `nightshift version --bump patch`,
`minor`, or `major` changes that value. A build identifier appends the selected
Git revision's UTC commit time, such as `0.1.0.2026-09-06-2312`.

Every factory invocation checks `origin/main` and prints the available build.
Create or refresh a dedicated test worktree without modifying the caller's
checkout:

```bash
nightshift sync --branch integration/nightshift
```

Branch-enabled runs deliberately use Codex's Git-metadata-capable sandbox;
pass `--branch none` when you need a workspace-write-only run with no branch,
commit, or push capability.

Use `./install.sh --runtime all --with-hook` to enable both Codex and Claude
Code. The default is `--runtime all`. Installs are symlinks by default, so a
`git pull` upgrades them; use `--copy` for read-only deployments.

Other modes:

| Flag | What it does |
|---|---|
| `--check` | Dry-run; report deps + conflicts + hook status |
| `--copy` | Plain copy instead of symlinks |
| `--with-hook` | Wire the scope-freeze + spec-guardrail (PreToolUse) and nightshift-stop-hook (Stop) into `~/.claude/settings.json` |
| `--runtime codex` | Install the Codex skill plus the shared `~/.nightshift` runtime |
| `--runtime local` | Same Codex skill; use it through Codex's Ollama loop |
| `--runtime claude` | Install Claude Code commands only |
| `--runtime all` | Install Codex and Claude Code support (default) |
| `--target DIR` | Override `~/.claude` (useful for testing) |
| `--codex-target DIR` | Override `~/.codex` (useful for testing) |
| `--nightshift-target DIR` | Override `~/.nightshift` (useful for testing) |
| `--bin-target DIR` | Install `nightshift` to this bin directory (default: `~/.local/bin`) |
| `--auth subscription\|api` | Persist auth preference; API still requires per-run launcher opt-in |
| `--unattended-shell` | Set Codex `approval_policy=never` and Claude Code `defaultMode=bypassPermissions` |
| `--uninstall` | Remove everything the installer placed |

Existing files are backed up to `~/.nightshift/.backup/<timestamp>/`.

### Portable manifest

`nightshift.toml` is the portable configuration source for the ticket provider, role-routing file, per-gate repair budgets, production target, and irreversible-action policy. Validate it before a run with `scripts/nightshift-manifest-validate.sh --project .`; validation emits JSON and refuses missing or invalid configuration. The production target must be an explicit HTTPS URL and cannot be inferred from a filename.

### Local models (after Codex)

The local path uses Codex's agent loop, so it consumes the same installed skill
and safeguards:

```bash
codex --oss --local-provider ollama -m <coding-model> -C /path/to/consumer-repo
```

Then use `$nightshift <ref>`. Choose a coding-oriented model with enough
context for a multi-stage workflow.

Or use the same one-call launcher:

```bash
nightshift gh:12 --provider local --model <coding-model>
```

### Confirmation policy

`AGENTS.md` makes the runtime-neutral core autonomous for normal non-destructive work:
reads, searches, edits, tests, commits, branches, and worktrees should continue
without a confirmation pause. It requires explicit confirmation immediately
before permanent deletion/removal (including history rewrites that remove
remote history) and production deployment. Pushes, PRs/merges, and dev/staging
deployments continue autonomously. Leave Codex on
`--unattended-shell` removes Codex and Claude Code permission dialogs for
factory sessions and direct use. The harness still requires a policy-level
production/removal confirmation; use it only on repositories and machines you
trust until the command-policy gateway in the dark-factory epic is implemented.

### Option B — Claude Code plugin

Add this repo as a plugin in `~/.claude/plugins/` or your plugin marketplace. The
`.claude-plugin/plugin.json` manifest exposes the commands directly. (You'll still want
the installer if you want the scope-freeze hook auto-wired, since plugins don't currently
ship hooks.)

---

## Dependencies

Required:
- `jq` — JSON parsing in the adapters
- `python3` — used by `nightshift-scope-freeze.sh` for glob matching
- [`bd`](https://github.com/gastownhall/beads) — beads CLI for the local engineering ledger
- `curl` — Jira / Monday / Notion / health-check fetches
- `git` — diff parsing for nightshift-drift / nightshift-review

Optional:
- `gh` — required for the `gh:` ticket source
- [`graphify`](https://github.com/safishamsi/graphify) — optional structural grounding pass
  during nightshift-product / nightshift-adversarial. Skipped silently if not on PATH.

`install.sh --check` reports what's missing.

---

## Recommended Claude Code settings

nightshift's stages are long, multi-turn runs that benefit from explicit context
discipline. Add these to `~/.claude/settings.json` to align Claude Code's defaults with
the pipeline's compaction strategy (see `docs/PIPELINE.md`):

```json
{
  "env": {
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

| Var | What it does |
|---|---|
| `MAX_THINKING_TOKENS=10000` | Caps extended-thinking budget per turn. Default 31999 burns ~70% more on internal reasoning than most pipeline stages need. |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` | Triggers auto-compaction at 50% of the context window instead of the default 95% — early enough that compaction lands near a stage boundary marker rather than mid-stage. |
| `CLAUDE_CODE_SUBAGENT_MODEL=haiku` | Subagents invoked by the `Task` tool (used heavily by nightshift-code-fact-extractor) run on Haiku. ~80% cheaper, sufficient for read-and-summarize work. |

These are the values nightshift's authors run with. None are required — the pipeline
works at Claude Code defaults. They just make each stage cheaper and the compaction
strategy land on the boundaries the pipeline marks for it.

---

## Ticket sources

`<REF>` formats accepted by `/nightshift-product` and `/nightshift-eng`:

| Format | Example | Required env |
|---|---|---|
| `gh:N` or `gh:owner/repo#N` | `gh:12`, `gh:acme/api#412` | `gh auth login` |
| `jira:KEY-N` | `jira:MVP-1` | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_TOKEN` |
| `monday:N` | `monday:1234567890` | `MONDAY_TOKEN` |
| `notion:<page-id>` | `notion:abc...` | `NOTION_TOKEN` |
| `bd:bd-abc` or bare `bd-abc` | `bd-a3f8e9` | local beads database |

Beads is auto-tried first for bare references. Add `~/.nightshift/scripts/nightshift-ticket-source.sh`
to your PATH if you want to call the adapter directly outside of Claude Code.

---

## What each stage does

| Stage | Reads | Writes | Gates on |
|---|---|---|---|
| `/nightshift-product` | ticket source | `docs/<task-key>/SPEC.md`, `docs/<task-key>/.bd-id`, beads mirror, tracker | spec exists with `## Sources` (enforced by `spec-guardrail` hook) |
| `/nightshift-adversarial` | SPEC.md | `<task-key>-citations.jsonl`, `SPEC-DIGEST.md`, `<task-key>-citations-trim.jsonl` | 0 unresolved `NOT_FOUND` claims |
| `/nightshift-implement` | SPEC-DIGEST, trimmed citations, scope-freeze | source files, `<task-key>.locks` (spec/red lock SHAs), RED-lock commits | tests green (or already-fixed-upstream SKIP) |
| `/nightshift-review` | git diff vs base, SPEC-DIGEST | `docs/<task-key>/REVIEW.md`, `review-history.jsonl` | TDD integrity PASS **and** 0 BLOCK at HIGH+MEDIUM confidence |
| `/nightshift-drift` | SPEC.md + git diff | `docs/<task-key>/DRIFT.md` | 0 BLOCK drift items |
| `/nightshift-qa` | project Playwright suite (via `nightshift-pw.sh`) | `docs/<task-key>/QA.md` | `PW_PASS` or `PW_SKIPPED` (no Playwright) |
| `/nightshift-preflight` | (interview) | `docs/<task-key>/PREFLIGHT.md` | PREFLIGHT.md exists |
| `/nightshift-deploy` | spec + tests + deploy config | `docs/<task-key>/DEPLOY.md`, PR | tests pass, CI green, health check OK |
| `/nightshift-batch` | ticket keys or source query | `batch-<ts>.json`, `batch-<ts>-retro.md`, `triage-<ts>.md` | each ticket runs `/nightshift-eng` autonomously; never blocks the batch |

All artifacts under `docs/<task-key>/` and `.nightshift/<task-key>.md`. Machine state
(lock SHAs, retry counters) lives in the `.nightshift/<task-key>.locks` sidecar. Existing
`.claude/task-progress` tasks remain readable and are updated in place when resumed, so the
human-readable tracker stays clean.

---

## Hard rules

- **Beads is the local engineering ledger, never the SSOT.** The upstream ticket stays
  the source of truth.
- **Canonical task key is the upstream ticket id.** All artifacts live under
  `docs/<task-key>/`. The bead id is internal — recorded in `docs/<task-key>/.bd-id`
  and used only for `bd note` / `bd close` calls.
- **No gstack.** Nightshift-pipeline never invokes `/ship`, `/land-and-deploy`, `/canary`,
  `/health`, gstack `/review`, `/qa`, or `/design-review`.

---

## Project layout

```
nightshift/
├── .claude-plugin/plugin.json   # Claude Code plugin manifest
├── commands/                     # 11 slash commands — the 9 nightshift-* stages plus
│                                 #   nightshift-spec and nightshift-preflight (vendored, no external deps)
├── agents/                       # role prompts the commands delegate to — runtime-neutral
│                                 #   (nightshift-code-fact-extractor, engineer, architect, nightshift-run-all-tests)
├── routing.json                  # role -> (provider, model) per gear; see "Agent routing"
├── scripts/                      # helpers: ticket-source, beads-mirror, scope-freeze,
│                                 #   spec-guardrail, claim-cache + TDD locks (spec/red/integrity),
│                                 #   token (spec-digest, context-check, citations-trim, tracker-trim),
│                                 #   batch (init/update/retro/triage/retry-increment/retry-exhaust),
│                                 #   lifecycle (dirty-check, scope-thaw, crash-check, stop-hook),
│                                 #   extractor-meta (citation timestamp + commit SHA),
│                                 #   dashboard (read-only local HTML snapshot, see "Dashboard")
├── docs/
│   ├── PIPELINE.md              # canonical pipeline reference
│   └── ARCHITECTURE.md          # design rationale
├── install.sh                    # idempotent installer with --check / --uninstall
└── LICENSE                       # MIT
```

---

## Agent routing

The `/nightshift-*` commands delegate to five named roles. Those role prompts ship in `agents/` and
are installed to `~/.nightshift/agents/`:

| Role | Invoked by | Job |
|---|---|---|
| `nightshift-code-fact-extractor` | `/nightshift-product`, `/nightshift-adversarial` | verify that identifiers cited in a spec exist in the codebase |
| `nightshift-spec-writer` | `/nightshift-product`, `/nightshift-spec` | produce the specification and source evidence |
| `nightshift-engineer` | `/nightshift-implement` (GREEN phase) | focused implementation, 1–2 files, single module |
| `nightshift-architect` | `/nightshift-implement` (GREEN phase) | multi-file / cross-module / escalated implementation |
| `nightshift-run-all-tests` | `/nightshift-implement` | run the unit+integration suite and report, read-only |

Role prompts carry **no `model:` key**. The active Bash+jq dispatcher reads the exact
`roles[role].gears[gear]` provider/model and `roles[role].prompt` from `routing.json`.
Gear defaults to 1 and must be 1–4; missing routes and malformed options fail before
launch. Copy and symlink installations include all five schemas and the local jq
validator alongside shared assets.

```bash
bash ~/.nightshift/scripts/nightshift-agent.sh nightshift-engineer \
  --gear 1 --in "task input.md" --out "task output.json"
bash ~/.nightshift/scripts/nightshift-agent.sh nightshift-code-fact-extractor \
  --gear 2 --in claims.md --out verification.json \
  --adversarial --author-provider claude
```

Claude receives an inline selected agent, role body and JSON schema. Codex uses
`exec --json --output-schema` and a separate final-message file; local uses the same
path with `--oss --local-provider ollama`. **Codex and local always use the read-only
sandbox.** Writing roles need a separately authorized integration to edit files;
dispatch does not expand their permissions. Routing effort/sandbox metadata does
not override these invocation constraints.

The Codex/local schema argument is a temporary projection without conditional
composition unsupported by OpenAI Structured Outputs. The checked-in schemas and
local validator retain the complete status-dependent requirements.

With `--adversarial` and `adversarial.cross_provider=true`, pass the actual author
provider from a prior normalized receipt. A different primary is retained;
otherwise the first different-provider entry in `adversarial.routes` is selected.
Missing author/alternate fails closed. Setting cross_provider false uses the normal
gear route. Available provider names are `claude`, `codex`, and `local`.

Every output has `status` (SUCCESS/FAIL/SKIP), `reason`, integer `attempts >= 1`,
`artifacts` (string branch, diff, provider and model), string-array `rules_fired`,
and `results`. Engineer/architect results contain `files_changed`; extractor results
contain `claims` with claim/status/file/line/inspected_files; test results contain
nonnegative passed/failed counts; writer results contain spec_path. Claims use
VERIFIED/NOT_FOUND/CONFLICT. SUCCESS tests require zero failed; successful writers
require a nonempty spec path. FAIL/SKIP need a reason. Unknown keys and invalid nested
types are rejected locally even if the provider claims schema enforcement.

Provider envelopes/events never become the output contract. Outputs publish
atomically; transport errors or invalid contracts replace stale success with a
normalized FAIL receipt and exit nonzero. Valid agent FAIL also exits nonzero;
SUCCESS/SKIP exit zero. Stage callers must still decide whether SKIP satisfies a
gate and verify actual evidence. Selected provider/model provenance is stamped by
the dispatcher. Offline mock regression coverage does not launch live providers.

### Namespacing is structural, not stylistic

### Runtime adapters

The files in `commands/`, `agents/`, `scripts/`, and `docs/` are the shared Nightshift core. Codex's skill and Claude compatibility command files only translate their host invocation into that core; the local/Ollama path uses the same Codex skill. No runtime owns a separate state machine or is canonical.

Everything nightshift installs carries a `nightshift-` prefix, and `install.sh` **refuses to install**
without one. `~/.claude/commands` remains a flat, single-slot Claude compatibility namespace shared
with every other plugin: an unprefixed name silently clobbers whoever installed first. The shared
runtime lives in `~/.nightshift/`, preventing another plugin's sync from writing its content into
this repository.

### Standalone by construction

nightshift invokes no command, agent, or script it does not ship. `/nightshift-spec` and
`/nightshift-preflight` are vendored rather than borrowed, so `/nightshift-eng` runs end to end on a machine
with nothing else installed.

**Runtime-neutral roles.** No `model:`
frontmatter, no Jira/ADO/Confluence side effects, no .NET assumptions, no cross-plugin script
paths, and every code-graph (`mex`) step routed through the capability probe so it no-ops when
mex is absent.

---

## Optional tools

`scripts/nightshift-capability.sh` probes what is available and caches the answer for 24h. Nothing in
this list is required; each has a defined fallback.

| Tool | Used for | Without it |
|---|---|---|
| `bd` (beads) | local engineering ledger | pipeline runs unchanged; no bead id, no `bd note` breadcrumbs. A `bd:*` ticket ref is the one exception — that ref shape needs beads. |
| `mex` | code graph, to locate symbols without reading files | agents fall back to Grep/Read/Glob |
| `gh` | ticket fetch for `gh:*` refs, CI polling, PR creation | those refs and `/nightshift-deploy`'s PR steps are unavailable |
| `jq` | JSON handling throughout | required in practice; `--check` reports it |
| Playwright | `/nightshift-qa`, E2E, deploy smoke | `nightshift-pw.sh` no-ops to PASS on projects without it |
| `claude` / `codex` / `ollama` | agent dispatch providers | at least one is needed to run any role |

```bash
bash ~/.nightshift/scripts/nightshift-capability.sh            # print the cached probe
bash ~/.nightshift/scripts/nightshift-capability.sh --refresh  # re-probe now
bash ~/.nightshift/scripts/nightshift-capability.sh --has mex  # exit 0/1, for guards
```

---

## Dashboard

`scripts/nightshift-dashboard.sh` renders a static, read-only HTML snapshot of durable
Nightshift batch status and controller gate receipt JSON. It is a local inspection tool,
not part of the pipeline — nothing calls it, and it cannot stop or alter a run.

**Dependencies:** `git` and `python3` only (both already required elsewhere in this
repo). No other runtime dependency is added.

**Invocation:**

```bash
scripts/nightshift-dashboard.sh --help
scripts/nightshift-dashboard.sh [--project DIR]                       # HTML to stdout
scripts/nightshift-dashboard.sh --project DIR > /tmp/dashboard.html   # save a copy
```

`--project` defaults to the current directory and must resolve to a Git checkout;
paths containing spaces are supported. There is no `--output` flag and the script never
writes to disk on its own — redirecting stdout is the only way a file gets created, and
that's the caller's choice, not the script's.

**What the snapshot shows:** the selected repository root, every worktree registered
against it (`git worktree list`), and — for each — its Nightshift state homes
(`.nightshift`, `.drew`, `.claude/task-progress`) and `docs/<task-key>/` artifact
directories, plus the repository-wide worktree ownership metadata under the shared
Git common directory. Rows are grouped by ticket/task but **never merged**: a batch
status entry, a controller gate receipt, and a worktree ownership receipt for the same
ticket each render as their own row with their own source link, so a terminal batch
entry can't visually paper over an active or failed gate receipt written later. Missing
or invalid fields render as `unknown`; malformed, oversized (>1 MiB), unreadable, or
wrong-shaped records render as visible per-record errors in their own table — they
never suppress the healthy rows around them, and an empty scan renders as an explicit
empty snapshot, never a fabricated success.

**Boundaries:** read-only local inspection and stdout output — no server, no network
call, no state write, no controller or factory invocation, no mutation control of any
kind. Discovery is bounded to six nested directory levels, 500 entries per directory,
10,000 entries overall, 1,000 records, and 1 MiB per JSON file; truncation is visible.
State receipts are discovered recursively and all regular files in task artifact
directories are linked. Discovery never follows a symlink outside the exact known
state, docs, or managed ownership directory roots, and paths found *inside* a JSON file's content are only ever used to
check whether a single file exists for linking — never as a new directory to scan.
Every link in the report is a `file://` URI built from a filesystem path this script
already verified exists as a plain regular file inside an allowed artifact root;
checkout secrets and arbitrary Git files are excluded; remote URLs
(including `pr_url` values) are shown as escaped text, never as links.

**Opening the report:** the HTML is a single self-contained file (inline CSS, no
external assets, a restrictive Content-Security-Policy, no `<script>` anywhere) — open
it directly from the filesystem in a browser, no local server required. Regenerate by
re-running the script; the report is a point-in-time snapshot, not a live view.

---

## License

MIT. See [LICENSE](LICENSE).

## Parallel work with managed worktrees

Prepare one checkout per ticket before writing specs, trackers, or code. The first default
base is the caller project's current HEAD; an explicit dependency always wins:

```bash
PROJECT=$(git rev-parse --show-toplevel)
FIRST=$(bash scripts/nightshift-worktree.sh prepare TASK-1 --project "$PROJECT")
SECOND=$(bash scripts/nightshift-worktree.sh prepare TASK-2 --project "$PROJECT" --base nightshift/TASK-1)
jq -r .worktree <<< "$FIRST"
jq -r .worktree <<< "$SECOND"
```

The deterministic branches are `nightshift/TASK-1` and `nightshift/TASK-2`, with checkouts
in the sibling `<repository-name>-worktrees/` directory. `--root DIR` selects a different
root outside the caller checkout. Change to the returned `.worktree` for all subsequent
stages and set `CLAUDE_PROJECT_DIR` to that path. Eng and batch do this before product
artifacts; standalone implement uses the same ownership contract. Pass `--base REF` through
eng/batch to stack work on an unmerged prerequisite.

Receipts live at `<common-git-dir>/nightshift/worktrees/TASK.json` and record repository,
branch, canonical path, base ref/SHA, dependency and status. Clean matching preparation is
idempotent and a resumed default retains its recorded base. Dirty reuse, changed explicit
bases, malformed receipts, unowned paths/branches, and repository mismatches stop with
reconciliation errors. Inspect the named receipt and retained resources; do not silently
adopt or overwrite them. A crash can leave a lock requiring ownership reconciliation.

There is one implementation per checkout. `nightshift-scope-activate.sh TASK --project PATH
--spec FILE` atomically acquires `.nightshift/.checkout-lease/owner` (or the resolved legacy
state home) and publishes only the spec allowlist plus that task's runtime artifact paths.
A collision names the owning task/tracker; separate worktrees have independent leases.

```bash
bash scripts/nightshift-worktree.sh finish TASK-1 --project "$PROJECT"
```

Finish is retain-only and repeatable: it keeps worktrees, branches, commits and dirty files,
and moves only matching lease/scope ownership into retained checkout retirement metadata.
Manual worktree/branch/file removal is a separate cleanup action requiring separate explicit
confirmation. Never reset, stash, remove, or force-checkout to repair receipt errors.

Run the offline aggregate suite with `bash evals/run-tests.sh`. It runs existing dispatch
regressions and eval unit/integration suites independently, continues after failures, and
returns failure if any suite fails or none exists. `--root DIR` supports isolated fixture
suite discovery. PR CI validates all target branches, including stacked feature branches.

## Static harness audit and opt-in monthly sampling

Run `scripts/nightshift-harness-audit.sh --project /absolute/project/path` for a
static artifact audit. Dependencies are Bash, Python 3.8+ (standard library,
including POSIX `fcntl` locking), and the adjacent shipped Nightshift helpers.
Git and jq support doctor diagnostics; provider CLIs and installed runtime
components are optional. `bd` is required only to file a monthly regression.
No provider/model or project test suite is invoked for scoring. These checks
prove artifact presence and content, not execution success or system health.

Each category contains two boolean checks worth 5 points each (0–10 total):

| Category | First check (5 points) | Second check (5 points) |
|---|---|---|
| `tool_coverage` | `capability_helper`: `scripts/nightshift-capability.sh` contains `--has` and `--refresh` | `provider_dispatch`: `scripts/nightshift-agent.sh` contains `routing.json`, `claude)` and `codex\|local)` |
| `context_efficiency` | `context_guard`: `scripts/nightshift-context-check.sh` contains `CLAUDE_CONTEXT_REMAINING_PERCENT` | `digest`: `scripts/nightshift-spec-digest.sh` contains `SPEC-DIGEST` |
| `quality_gates` | `review_integrity`: `commands/nightshift-review.md` contains `nightshift-tdd-integrity-check.sh` | `drift_gate`: `commands/nightshift-drift.md` contains `BLOCK` |
| `memory_persistence` | `state_resolver`: `scripts/nightshift-state-dir.sh` contains `.nightshift` and `.claude/task-progress` | `trend_log`: `commands/nightshift-review.md` contains `review-history.jsonl` and `timestamp` |
| `eval_coverage` | `state_tests`: `tests/test-state-dir.sh` contains `assert_eq` and `nightshift-state-dir.sh` | `dispatch_tests`: `tests/test-agent-dispatch.sh` contains `nightshift-agent.sh` and `test -f` |
| `security_guardrails` | `scope_guard`: `scripts/nightshift-scope-freeze.sh` contains `.active-scope` and `BLOCKED` | `spec_guard`: `scripts/nightshift-spec-guardrail.sh` contains `## Sources` and `## Model Router` |
| `cost_efficiency` | `routing_gears`: `routing.json` is an object with nonempty `roles`, each with a nonempty `gears` object | `review_cache`: `commands/nightshift-review.md` contains `DIFF_SHA` and `CACHE_HIT` |

Scored files must be readable nonempty regular files. Symlinks count only when
resolved inside the project. Missing or malformed artifacts fail their own
checks. Host tools, timestamps and doctor findings cannot change these scores.

Every valid run prints one compact JSON envelope and appends that same physical
line to `harness-history.jsonl` under the state directory resolved by the shipped
`nightshift-state-dir.sh` (canonical `.nightshift`, with existing `.drew` or
`.claude/task-progress` fallback). Its schema includes `schema_version:1`,
`task:"harness-audit"`, UTC `timestamp`, `mode:"audit"` or `"monthly"`,
`cache_hit:false`, seven-category `scores`, `deltas`, fourteen boolean `checks`,
and category `counts` with `BLOCK:0`, `WARN` equal to failed checks, and `NOTE:0`.
`doctor` contains `ok` and named records with boolean `ok` and an `explanation`;
`bead` contains the filing status and applicable receipt fields. All history rows
are validated before comparison or append. Malformed/truncated history causes a
visible failure and is never silently skipped or rewritten. A per-history POSIX
lock covers reading, comparison, bead lookup/creation, and append.

Ordinary deltas compare against the latest timestamped earlier sample. Add
`--monthly` to compare only with the immediately preceding UTC calendar month's
latest sample, excluding pending monthly filings. Regressions are exactly deltas
below -1. A first run establishes history; without a previous-month sample all
deltas are null and no regression can be detected. Manual audits can supply the
previous month's sample. `NIGHTSHIFT_AUDIT_NOW=YYYY-MM-DDTHH:MM:SSZ` overrides the
UTC clock for deterministic offline use; invalid timestamps fail before history
mutation.

Monthly filing uses external ref `nightshift:harness-audit:YYYY-MM` in the audited
project's local beads database. It checks `bd list --all --limit 0 --json` for an
exact external-ref match (including closed beads) before creation. Successful
history receipts also prevent duplicate creation. The description records each
category's current score, prior score and delta. `bead.status` is
`not_requested` for manual audits, `not_needed` without regressions, `created`
after creation, or `existing` after reconciliation. Monthly receipts include
`month` and `external_ref`; successful filing includes `id`. Missing/unusable bd,
failed lookup/create, malformed output or missing IDs leave `status:"pending"`
with an `error`, persist the score row, and exit nonzero. Retry the same monthly
command after fixing the dependency: it reconciles by exact external ref,
including after an interrupted create, and never treats a failed filing as done.

Doctor inspects provider availability through the trusted adjacent capability
helper, installed Nightshift skills/commands under `${CODEX_HOME:-$HOME/.codex}`
and `$HOME/.claude`, hook references, the manifest through the shipped validator,
git worktree support, and conflicting legacy installed instructions. Compatibility
adapters are allowed. Routing is parsed as data; routing commands, hooks and
instructions are not executed. `--refresh` asks only the trusted capability helper
to refresh its cache. Optional absent runtime components can leave doctor
`ok:false` while the audit still exits zero. These are diagnostics, not automatic
installation or repairs.

To prepare a persistent schedule, run:

```sh
scripts/nightshift-harness-audit-cron.sh --project /absolute/persistent/project
```

The helper prints a two-line crontab snippet with a fixed bootstrap
`PATH=/usr/bin:/bin` and a `0 9 1 * *` command. The command uses absolute
`/usr/bin/env` with one shell-quoted `PATH=<captured value>` argument to restore
the exact captured effective PATH before invoking the absolute audit/project
paths with `--monthly --refresh`. This preserves both quote kinds, whitespace
and shell metacharacters without exposing them to cron's environment parser.
Shell arguments are quoted and command percent signs are escaped for cron; paths
and PATH containing newlines are rejected. The command works from an unrelated
working directory with that captured effective PATH. Copy the generated
snippet into a persistent host scheduler to activate it. The helper never reads
or writes your crontab, and opening or merging this PR does not activate a
schedule. The schedule is first-of-month 09:00 in the host cron timezone; audit
month boundaries use UTC. Prefer a UTC scheduler where available.

## Failure memory and adoption evidence

`scripts/nightshift-failure-memory.sh` is an offline, read-only reporter using Bash
and Python 3 standard library. Select a JSONL bundle of controller receipts and a
learning registry explicitly; the reporter does not discover runs automatically.

```sh
scripts/nightshift-failure-memory.sh --project /path/to/project \
  --receipts evidence/controller-receipts.jsonl --learnings evidence/learnings.json
```

All three options are required exactly once. Both input file names must be
project-relative. Absolute file names, `..` components, symlink escapes, missing,
unreadable, empty, and nonregular files are rejected. In-project symlinks to
nonempty regular files are allowed. Successful input emits one compact,
deterministic JSON line and exits zero, including when learnings are unsupported.
Invalid input exits nonzero with the fixed diagnostic
`nightshift-failure-memory: invalid input`, empty stdout, and no raw input values.
Duplicate JSON keys and nonfinite numbers are rejected, including in discarded
fields. No mechanism, command, provider, model, subprocess, adoption step, history
write, or scheduler change is executed. Inputs remain unchanged.

Each receipt requires `ticket` (nonempty string), `generated_at` (valid exact UTC
`YYYY-MM-DDTHH:MM:SSZ`), `gate` (`implement`, `review`, `drift`, `qa`), `provider`
(`codex`, `claude`, `local`), `status` (`complete`, `failed`, `blocked`,
`needs-decision`), `attempts` (array), and `next_action` (string). Each attempt must
contain exactly one positive integer `attempt` or `repair_after_attempt`, plus
integer `exit_code` from 0 through 255; booleans are not integers. The last ordinary
attempt determines the exit code. A complete receipt must end in ordinary exit 0;
failed/needs-decision must end in ordinary nonzero exit. Blocked may have no
attempts. Other fields are discarded, including output and command text.

Identity is SHA256 of UTF-8 compact, sorted-key JSON containing `ticket`,
`generated_at`, `gate`, and `provider`. JSON encoding uses ASCII escapes and no
spaces (`ensure_ascii=True`, separators `,` and `:`). Only the resulting
`evidence_id` hash is exposed. Identical projected duplicates count once even when
private output differs. Conflicting status, selected exit code, or next-action
category for the same identity invalidates the bundle.

Each noncomplete receipt has a structural signature: SHA256 of JSON encoded the
same way, containing `gate`, `provider`, `status`, `exit_code` (null if absent),
and `next_action_category`. Exact category mappings are:

| Controller next action | Category |
| --- | --- |
| `continue to the next gate` | `continue` |
| `inspect the final gate output and repair the smallest in-scope cause` | `inspect-and-repair` |
| `Configure NIGHTSHIFT_WORKER_IMAGE; host execution is disabled.` | `configure-isolation` |
| Any other text | `other` |

Clusters expose those structural fields, `signature`, `count`, `repeated`
(count at least two), and sorted `evidence_ids`. Single failures remain visible.
Structural agreement does not establish a shared root cause. Ticket names,
commands, output, worktrees, free next-action text, changed files, and unknown
receipt fields never appear in the report.

A registry has this exact required shape (hashes below are placeholders to replace
with actual reported hashes):

```json
{
  "schema_version": 1,
  "learnings": [{
    "id": "qa-guard-1",
    "signature": "0000000000000000000000000000000000000000000000000000000000000000",
    "adopted_at": "2026-09-06T12:00:00Z",
    "kind": "guardrail",
    "mechanism": "guards/qa-rule.json",
    "evidence": [
      "1111111111111111111111111111111111111111111111111111111111111111",
      "2222222222222222222222222222222222222222222222222222222222222222"
    ],
    "validation": "evidence/qa-guard-1.validation.json"
  }]
}
```

IDs must be unique and match `[A-Za-z0-9][A-Za-z0-9_.-]*`; signatures are 64
lowercase hexadecimal characters. Kinds are `test`, `guardrail`, `fixture`,
`manifest`, or `prompt`. Malformed entry types invalidate input. Missing adoption
mechanism/evidence/validation yields an unsupported finding. Evidence must name
at least two distinct matching failure IDs strictly before adoption; every named
ID must exist and have the selected signature. A `prompt` is always unsupported
with reason `prompt_only`, even if accompanied by a passed validation file.

The validation file binds actual mechanism bytes to recorded checks:

```json
{
  "schema_version": 1,
  "status": "passed",
  "mechanism": "guards/qa-rule.json",
  "sha256": "3333333333333333333333333333333333333333333333333333333333333333",
  "evidence": [
    "1111111111111111111111111111111111111111111111111111111111111111",
    "2222222222222222222222222222222222222222222222222222222222222222"
  ],
  "validated_at": "2026-09-06T11:00:00Z"
}
```

The mechanism must be a readable, nonempty regular file confined to the project.
Validation must itself be confined, pass strict JSON parsing, name exactly the
same mechanism path and evidence set, and contain the current mechanism SHA256.
Its UTC timestamp must be no earlier than the latest named evidence and no later
than adoption. A stale hash, failed status, missing/malformed validation, escaped
path, or evidence mismatch cannot establish support. Reasons are fixed codes:
`prompt_only`, `missing_mechanism`, `missing_evidence`, `missing_validation`,
`duplicate_evidence`, `insufficient_evidence`, `unknown_evidence`,
`evidence_signature_mismatch`, `evidence_not_prior`, `invalid_mechanism`, or
`invalid_validation`. The first applicable reason is returned. Invalid reference
text is never echoed.

Adopt changes in stages: select the receipt bundle and inspect clusters with an
empty registry (`{"schema_version":1,"learnings":[]}`); implement the mechanism
separately; run its real test or guardrail independently; record passed validation
with its actual content hash, matching evidence IDs, and validation time; then
record adoption and rerun this reporter. The reporter only verifies recorded
validation data. It neither runs the check nor proves that the change works.

The report shape is `schema_version:1`, deduplicated `receipt_count`, `clusters`
sorted by signature, and `learnings` sorted by ID. Each learning contains `id`,
`signature`, `status` (`supported`/`unsupported`), `reasons`, `evidence`, and
`outcomes`. Supported entries additionally expose
`mechanism:{kind,path,sha256}` and outcomes `{status,before,after}`. Each cohort
has `total_runs`, `completed_runs`, `recurrences`, `completion_rate`, and
`recurrence_rate`; empty-cohort rates are null. Unsupported outcomes are only
`{"status":"unknown"}`, with no claimed rates or mechanism path/hash.

Comparable cohorts use all deduplicated selected receipts having the signature's
same gate **and** provider, strictly before and strictly after adoption. Receipts
exactly at adoption are excluded. `improved`, `regressed`, and `unchanged` compare
completion rates; `insufficient_evidence` means either cohort is empty. Exact
signature recurrence is reported separately. Different ticket mixes can change
these observations, so neither validation nor improved completion establishes
causality. Selecting additional subsequent receipts updates outcomes without
mutating anything. Input ordering never changes report ordering or counts; no
current-clock metadata is added.

Run offline regression coverage separately with `bash evals/run-tests.sh`, which
discovers the repository's `test-*.sh` suites. Reporting never runs those suites.
