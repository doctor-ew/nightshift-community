---
name: nightshift-batch
description: "Autonomous batch runner — triages a set of candidate tickets, then runs each one through the full /nightshift-eng pipeline sequentially and unattended, recording per-ticket outcomes and writing an aggregate retro. Resumable from its state file. Run /nightshift-batch <tickets-or-query> [--batch-n N] [--resume <file>]."
argument-hint: "\"MVP-1,MVP-2,MVP-3\"  |  \"<source query>\"  |  --resume batch-YYYYMMDD-HHMM.json"
---

# /nightshift-batch — Autonomous Batch Pipeline

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

Runs `/nightshift-eng` over many tickets in one unattended pass. Each ticket flows through the full
pipeline (product → adversarial → implement → review → drift → preflight → deploy) in
**autonomous mode**; outcomes are recorded to a batch state file and summarized in a retro.

**Batch implies autonomous.** Every `/nightshift-eng` invocation here runs with `AUTONOMOUS=true`,
so the stages take their non-interactive paths (conservative approach, JSON contracts, retry
budgets) instead of stopping at human gates. There is no per-ticket human approval — that is
the point. Review the **triage report** and the **retro**, not each ticket live.

**No gstack.** This orchestrator only calls `/nightshift-eng` and the `nightshift-*` scripts.

---

## Usage

```
/nightshift-batch "MVP-1,MVP-2,MVP-3"            — explicit list (skips triage)
/nightshift-batch "dp-g45.4 dp-g45.5"            — local Beads IDs (skips triage)
/nightshift-batch "project=MVP AND status=Open"  — source query → triage → batch
/nightshift-batch "project=MVP" --batch-n 10      — fetch/triage up to 10
/nightshift-batch --resume batch-20260607-1527.json  — resume a prior batch
```

---

## Step 1 — Parse arguments

```bash
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CONTROLLER_PROJECT=$(cd "$PROJECT" && pwd -P)
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "$ARGUMENTS") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
ARG=$(jq -r '.arguments' <<< "$STAGE_ARGS")
BATCH_N=5; RESUME_FILE=""
echo "$ARG" | grep -q -- "--batch-n" && BATCH_N=$(echo "$ARG" | sed -n 's/.*--batch-n \([0-9]*\).*/\1/p')
echo "$ARG" | grep -q -- "--resume"  && RESUME_FILE=$(echo "$ARG" | sed -n 's/.*--resume \([^ ]*\).*/\1/p')
# Factory options are policy for each ticket, not part of the ticket list.
# Keep their values for Step 4, but remove them before list/query classification.
BRANCH=$(echo "$ARG" | sed -n 's/.*--branch \([^ ]*\).*/\1/p')
[ -z "$BRANCH" ] && BRANCH="auto"
PUSH=false; echo "$ARG" | grep -q -- '--push' && PUSH=true
OPEN_PR=false; echo "$ARG" | grep -q -- '--pr' && OPEN_PR=true
INPUT=$(echo "$ARG" | sed -E 's/--batch-n [0-9]+//; s/--resume [^ ]+//; s/--branch [^ ]+//; s/--push//g; s/--pr//g' | xargs)
```

Empty `$INPUT` and no `--resume` → print usage and stop.

---

## Step 2 — Resolve the ticket list

**Resume:** if `--resume` is set, skip straight to Step 3 with that file.

**Explicit list:** run the deterministic resolver. It accepts comma- or whitespace-separated
references, existing task keys, source-prefixed references, and bare IDs that `bd show` resolves.
Bare Beads IDs are normalized to `bd:<id>` so the per-ticket run creates its task folder instead
of incorrectly attempting a resume without artifacts. A resolver exit of `2` means `$INPUT` is a
query; any other non-zero exit is fatal.

```bash
set +e
TICKET_LIST=$(bash ~/.nightshift/scripts/nightshift-batch-resolve.sh --input "$INPUT")
RRC=$?
set -e
if [ "$RRC" -eq 0 ]; then
  SOURCE=explicit
elif [ "$RRC" -ne 2 ]; then
  echo "Batch explicit-list resolver failed."
  exit "$RRC"
fi
```

**Query:** only when `RRC=2`, set `SOURCE=jql`. Fetch up to `$BATCH_N` candidate tickets via the configured
source (the same adapter `/nightshift-product` uses, or an MCP search), and normalize them to:

```json
{ "issues": [ { "key": "MVP-1", "fields": { "summary": "...", "description": "..." } } ] }
```

Write that to a temp file and triage it:

```bash
TRIAGE_TMP=$(mktemp /tmp/nightshift-batch-triage.XXXXXX.json)
# ... write normalized candidate JSON to $TRIAGE_TMP ...
set +e
TICKET_LIST=$(bash ~/.nightshift/scripts/nightshift-triage.sh --n "$BATCH_N" --query "$INPUT" --input "$TRIAGE_TMP")
TRC=$?
set -e
rm -f "$TRIAGE_TMP"
if [ "$TRC" -eq 2 ]; then
  echo "No tickets passed triage gates — refine the query or relax criteria. See the triage report."
  exit 0
fi
```

`TICKET_LIST` is the newline/!comma list of passing keys. The triage report path is on stderr.

---

## Step 3 — Initialize (or resume) batch controller state

Keep `CONTROLLER_PROJECT` fixed and preserve the helper's repository-relative `STATE_REL`.
Controller bookkeeping may be initialized here; ticket product artifacts, sentinels,
trackers and scopes must wait for that ticket's isolation gate in the loop. Every batch
init/update/retro helper explicitly uses the controller project even while the ticket
pipeline runs in another checkout. Never pass an absolute path as `--state`.

```bash
if [ -n "$RESUME_FILE" ]; then
  INIT=$(env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-init.sh --resume "$RESUME_FILE")
else
  LIST_CSV=$(echo "$TICKET_LIST" | tr '\n' ',' | sed 's/,$//')
  INIT=$(env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-init.sh \
    --tickets "$LIST_CSV" --source "$SOURCE" --source-value "$INPUT" --batch-n "$BATCH_N")
fi
STATE_REL=$(echo "$INIT" | grep '^BATCH_STATE_PATH:' | awk '{print $2}')
RESUME_FROM=$(echo "$INIT" | grep '^RESUME_FROM:' | awk '{print $2}')   # empty on fresh start
TICKETS=$(echo "$INIT" | grep '^BATCH_TICKET:' | awk '{print $2}')
echo "Batch state: $CONTROLLER_PROJECT/$STATE_REL"
```

---

## Step 4 — Per-ticket loop

Before entering the loop, read `${CONTROLLER_PROJECT}/${STATE_REL%.json}-decisions.md`
if present. This is a coordinating-agent handoff of delegated product choices,
not permission to bypass safety gates. Carry its resolved choices into each
ticket spec; do not repeat preference questions already answered there.

For each `TICKET` in `$TICKETS`, in order (if `RESUME_FROM` is set, skip until you reach it):

**a.** Skip if its status in `$CONTROLLER_PROJECT/$STATE_REL` is already `complete` or `skipped`:
```bash
ST=$(jq -r --arg k "$TICKET" '.statuses[$k].status // "pending"' "$CONTROLLER_PROJECT/$STATE_REL")
[ "$ST" = "complete" ] && continue
[ "$ST" = "skipped" ]  && continue
```

**b.** Prepare only this ticket now. Resolve its stable task key read-only. Accept
`--base REF` as a literal option (remove it before ticket/query parsing); a per-ticket
prerequisite takes precedence over the batch default. Wait until preceding prerequisites
have passed their gates, then resolve their actual verified branch head through prepare.
Do not pre-create all worktrees at batch initialization: doing so would capture stale
prerequisite commits. If a prerequisite fails, record this ticket's dependency failure and
continue with independent tickets without preparing the dependent ticket.

```bash
BASE_ARGS=()
COMMON_DIR=$(git -C "$CONTROLLER_PROJECT" rev-parse --path-format=absolute --git-common-dir)
if [ -f "$COMMON_DIR/nightshift/worktrees/$TASK_KEY.json" ]; then
  # A prerequisite is a containment requirement, not a request to change the
  # immutable base of an existing receipt. The helper verifies ancestry.
  [ -z "${TICKET_BASE_REF:-}" ] || BASE_ARGS+=(--requires "$TICKET_BASE_REF")
  [ -z "${BASE_REF:-}" ] || BASE_ARGS+=(--base "$BASE_REF")
else
  [ -z "${TICKET_BASE_REF:-${BASE_REF:-}}" ] || BASE_ARGS=(--base "${TICKET_BASE_REF:-$BASE_REF}")
fi
if ! WORKTREE_RECEIPT=$(bash ~/.nightshift/scripts/nightshift-worktree.sh prepare "$TASK_KEY" \
  --project "$CONTROLLER_PROJECT" "${BASE_ARGS[@]}"); then
  env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-update.sh \
    --state "$STATE_REL" --ticket "$TICKET" --status failed --reason "worktree isolation failed"
  continue
fi
PROJECT=$(printf '%s\n' "$WORKTREE_RECEIPT" | jq -er '.worktree') || exit 1
cd "$PROJECT" || exit 1
export CLAUDE_PROJECT_DIR="$PROJECT"
export NIGHTSHIFT_PREPARED_TASK="$TASK_KEY"
export NIGHTSHIFT_WORKTREE_RECEIPT="$WORKTREE_RECEIPT"
env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-update.sh \
  --state "$STATE_REL" --ticket "$TICKET" --status in_progress
```

Record branch, receipt path, base SHA and dependency in the isolated task tracker after
this gate. Never infer main/master. On resume validate a matching prepared context as
described by standalone implement instead of repeating clean-only prepare after this
ticket has written its own in-progress artifacts. Do not adopt unrelated dirty resources.

**c.** Run the pipeline **autonomously** for this ticket.
If the prepared receipt contains `migration`, inspect that journal's retained
`spec_source` when present (verify its `spec_hash` before reuse), as well as its
legacy worktree diff and spec as historical evidence. Reconcile useful changes
against the current base; do not blindly copy stale prerequisite decisions or
treat archived progress as current gate completion.
If it contains `refresh_history`, inspect the latest snapshot's `artifacts`
directory as historical task evidence and re-ground it against the refreshed
base. Do not mark old gates passed or blindly restore obsolete artifacts.

Set `AUTONOMOUS=true` and `NIGHTSHIFT_FACTORY_MODE=true` in the environment for the invocation and call `/nightshift-eng <TICKET> --base <prepared receipt base_sha>` in the validated prepared context.
Pass the receipt's immutable `base_sha`, not the prerequisite branch SHA, to
eng/implement ownership validation. Step b has separately checked prerequisite
inclusion. Record the required prerequisite ref/SHA in the tracker alongside the
base SHA; these may legitimately differ when integration already contains it.
Apply `BRANCH`, `PUSH`, and `OPEN_PR` independently to that ticket; do not ask for a repository,
base branch, or routine branch/PR confirmation. The factory skill defines the branch policy.
Nightshift-eng's stages take their non-interactive paths; routine gate failures receive up to three
small, in-scope repair attempts before the ticket receives a failure receipt. `/nightshift-implement`
returns the Step 9 JSON contract that tells you the outcome.

> Context hygiene: each ticket is an independent pipeline. If the context budget is low between
> tickets (`nightshift-context-check` warns), `/compact` before starting the next one — the batch
> state file is the durable record, so a compact mid-batch loses nothing.

**d.** Record the outcome by what `/nightshift-eng` produced for this ticket:

| Signal | Update |
|---|---|
| Pipeline completed successfully (PR URL optional) | `--status complete --receipt "<receipt-path>" [--pr-url "<url>"]` |
| Controller receipt status `blocked`, or tracker `❌ BLOCKED` | `--status blocked --receipt "<receipt-path>" --reason "<reason>"` |
| Controller receipt status `needs-decision` | `--status needs-decision --receipt "<receipt-path>" --reason "<reason>"` |
| Controller receipt status `failed`, or an unexpected error | `--status failed --receipt "<receipt-path>" --reason "<reason>"` |
| `PIPELINE_SKIPPED:` emitted (already-fixed-upstream or explicit skip) | `--status skipped --receipt "<receipt-path>" --reason "<reason>"` |

Preserve the controller's explicit terminal status: retry exhaustion is `failed`, `blocked`,
or `needs-decision` as recorded in its receipt. A gate's `complete` status advances the
pipeline; mark the ticket `complete` only after all required gates finish. Supply the
terminal evidence artifact with `--receipt`; the helper stores a `receipt` field on every
terminal entry (an empty string if no artifact exists). Metrics include separate `blocked`
and `needs-decision` counts. Updating a ticket preserves other entries and clears the
current pointer only when it names that ticket.

```bash
env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-update.sh --state "$STATE_REL" --ticket "$TICKET" \
  --status <complete|skipped|failed|blocked|needs-decision> [--pr-url <url>] [--reason "<reason>"] [--receipt "<receipt-path>"]
echo "[batch] $TICKET: <status>"
```

On completion, use `nightshift-worktree.sh finish "$TASK_KEY" --project "$PROJECT"`
(idempotent if eng already finished). Retain the worktree/branch and retire only matching
scope/lease state. Restore the controller context before selecting the next ticket:

```bash
cd "$CONTROLLER_PROJECT" || exit 1
PROJECT="$CONTROLLER_PROJECT"
export CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT"
unset NIGHTSHIFT_PREPARED_TASK NIGHTSHIFT_WORKTREE_RECEIPT
```

**e.** A `failed`, `blocked`, `needs-decision`, or `skipped` ticket does **not** stop the batch — record it and continue to
the next ticket. Only a fatal harness error (e.g. `jq` missing) aborts the run.

---

## Step 5 — Aggregate retro

```bash
RETRO=$(env CLAUDE_PROJECT_DIR="$CONTROLLER_PROJECT" bash ~/.nightshift/scripts/nightshift-batch-retro.sh --state "$STATE_REL" | grep '^BATCH_RETRO:' | awk '{print $2}')
```

---

## Step 6 — Summary

```
[batch] Complete: <M> complete, <K> skipped, <J> failed, <B> blocked, <D> needs-decision of <N> total.
State: <CONTROLLER_PROJECT>/<STATE_REL>
Retro: <RETRO>
Triage: <triage report path, if a query run>
```

Read `.metrics` from `$CONTROLLER_PROJECT/$STATE_REL` for the counts. Stop here — `/nightshift-batch` never proceeds past the
loop into a single-ticket pipeline.

---

## Resume semantics

Re-running `/nightshift-batch --resume <file>` reads the state file, finds the first ticket not yet
`complete`/`skipped`, and continues from there. `complete` and `skipped` tickets are never
re-run; `failed`, `blocked`, and `needs-decision` tickets are terminal for the current pass
but **are** retried on explicit resume. Per-ticket commits of
the state file mean a crash mid-batch loses at most the in-flight ticket.
