---
name: nightshift-eng
description: "Full pipeline orchestrator — chains nightshift-product → nightshift-adversarial → /nightshift-implement (with scope freeze) → nightshift-review → nightshift-drift → /nightshift-preflight → nightshift-deploy. Each stage gates the next. Resumable across sessions via .nightshift/<task-key>.md with legacy compatibility. Run /nightshift-eng <REF-or-task-key>."
argument-hint: "<REF-or-task-key> — e.g., gh:12, jira:MVP-1, MVP-1 (resume), bd-abc123 (resume by bead), MVP-1 --abandon (cancel + clean up)"
---

# /nightshift-eng — Pipeline Orchestrator

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

Runs the full nightshift-* pipeline end to end. Each stage is its own slash command; this
orchestrator just chains them and enforces the gates between.

**Pipeline:**
```
nightshift-product       (ticket → spec, mirror to beads)
   └─ gate: spec exists with verified ## Sources
nightshift-adversarial   (claim verification → seals nothing; emits SPEC-DIGEST + trimmed citations)
   └─ gate: 0 unresolved NOT_FOUND claims
nightshift-implement     (TDD build: spec-lock → RED under firewall → red-lock → GREEN; scope-freeze active)
   └─ gate: implementation completes (tests green)
nightshift-review        (TDD integrity gate, then DRY/SOLID/ACID/CoC/BigO/LLM-trust over the digest)
   └─ gate: TDD integrity PASS  AND  0 BLOCK findings (HIGH+MEDIUM confidence)
nightshift-drift         (spec ↔ diff drift check)
   └─ gate: 0 BLOCK drift items
nightshift-qa            (behavioral QA — full Playwright suite; no-op/PASS when absent)
   └─ gate: PW_PASS or PW_SKIPPED
/nightshift-preflight         (pre-deploy checklist)
   └─ gate: PREFLIGHT.md exists
nightshift-deploy        (ship + @smoke Playwright against the live URL)
   └─ done: bead closed, PR merged, health check OK, smoke clean
```

Each gate that fails leaves the tracker in a resumable state — re-run `/nightshift-eng <task-key>`
later and it picks up at the failed stage. Every stage runs a context-budget check on entry
(`nightshift-context-check`) and bails to a `--from <stage>` resume hint before hitting a context wall.

**Many tickets at once?** `/nightshift-batch "<keys-or-query>"` triages a set and runs each one
through this pipeline autonomously, then writes an aggregate retro. See `commands/nightshift-batch.md`.

---

## First-time setup

```bash
git clone https://github.com/doctor-ew/nightshift-community.git
cd nightshift-community
bash install.sh --auth subscription --with-hook
```

Run `--check` first to audit what's missing without making changes.

- **Symlink install** — keep the cloned repo around; `git pull` in it upgrades all installations in place.
- **Required deps** (installer flags if absent): `bd`, `jq`, `python3`, `curl`, `git`
- **Optional deps**: `gh`, `graphify`
- **Scope-freeze hook** — won't fire until `nightshift-eng` writes `.active-scope-<task-key>`, so enabling globally from the start is safe.
- **Project access** — authenticate GitHub for your own practice repository.
  Public installation does not require collaborator access to Nightshift.

---

**Hard rules:**
- **No gstack.** This orchestrator never invokes `/ship`, `/land-and-deploy`, `/canary`,
  `/health`, `/review` (gstack), `/qa`, `/design-review`, `/autoplan`, or any other
  gstack-namespaced skill. Every stage is a `nightshift-*` skill (including `/nightshift-implement`) or
  `/nightshift-preflight` (both local, neither gstack).
- **One task-key, one pipeline run.** The upstream ticket id is the canonical task key
  (e.g., `MVP-1`, `12`, the Monday item id). The bead id is internal — recorded in
  `docs/<task-key>/.bd-id` and used only for `bd note` / `bd close` calls. All artifacts
  go under `docs/<task-key>/`. All new progress is in `.nightshift/<task-key>.md`; legacy runs remain in `.claude/task-progress/`.

---

## Usage

```
/nightshift-eng gh:12 --base nightshift/prerequisite — start on an explicit dependency
/nightshift-eng jira:MVP-1     — start fresh from Jira MVP-1
/nightshift-eng MVP-1          — resume by task key (folder docs/MVP-1/ exists)
/nightshift-eng bd-abc123      — resume by bead id (looks up task key via docs/*/.bd-id)
/nightshift-eng MVP-1 --from review   — re-run from a specific stage
```

---

## Step 1 — Resolve task key

```bash
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --shell) || exit $?
eval "$PROJECT_CONTEXT"
PROJECT="$NIGHTSHIFT_PROJECT_DIR"
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "$ARGUMENTS") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
ARG=$(jq -r '.arguments' <<< "$STAGE_ARGS")
FROM_STAGE=""; ABANDON=0; REF=""; BASE_ARGS=()
# Ticket refs and Git refs contain no whitespace. Read tokens literally; never eval.
read -r -a TOKENS <<< "$ARG"
set -- "${TOKENS[@]}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --base|--from)
      [ "$#" -ge 2 ] || { echo "Missing value for $1" >&2; exit 1; }
      if [ "$1" = --base ]; then BASE_ARGS=(--base "$2"); else FROM_STAGE=$2; fi
      shift 2 ;;
    --abandon) ABANDON=1; shift ;;
    --*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) [ -z "$REF" ] || exit 1; REF=$1; shift ;;
  esac
done
DOCS_DIR="${PROJECT}/docs"

TASK_KEY=""
ROUTE_FRESH=0

# Preserve local input location before entering an isolated worktree.
if [[ "$REF" == spec:* ]] || [ -f "$REF" ]; then
  REF="spec:$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1].removeprefix("spec:")).resolve(strict=True))' "$REF")" || exit 1
fi

# (1) Source-prefixed ref → fresh run via nightshift-product
if echo "$REF" | grep -qE '^(gh|jira|monday|notion|bd|spec):'; then
  ROUTE_FRESH=1
  # Read-only normalized ticket lookup; do not mirror or write product artifacts yet.
  TICKET_JSON=$(bash ~/.nightshift/scripts/nightshift-ticket-source.sh "$REF") || exit 1
  TASK_KEY=$(printf '%s\n' "$TICKET_JSON" | jq -er '.source_id | select(. != null) | tostring') || exit 1

# (2) Bare ref that matches an existing task folder → resume by task key
elif [ -f "${DOCS_DIR}/${REF}/SPEC.md" ]; then
  TASK_KEY="$REF"

# (3) Bare ref that resolves as a beads issue → resume by bead, look up task key
elif bd show "$REF" --json >/dev/null 2>&1; then
  TASK_KEY=$(grep -lr "^${REF}$" "${DOCS_DIR}"/*/.bd-id 2>/dev/null \
    | sed -E "s|.*/docs/([^/]+)/\.bd-id|\1|" | head -1)
  if [ -z "$TASK_KEY" ]; then
    echo "ORCHESTRATOR_BLOCKED: bead ${REF} exists but no docs/*/.bd-id points to it."
    echo "  Run /nightshift-product bd:${REF} to create the task folder, or pass the task key directly."
    exit 1
  fi

else
  echo "ORCHESTRATOR_BLOCKED: cannot resolve '${REF}'."
  echo "  - Use a source prefix for fresh tickets: gh:N | jira:KEY-N | monday:N | notion:ID"
  echo "  - Or pass an existing task key (folder docs/<key>/SPEC.md must exist)"
  echo "  - Or pass a bare bead id that has been mirrored into a task folder"
  exit 1
fi
```

If empty `$REF`: print `"Usage: /nightshift-eng <ref-or-task-key> [--from <stage>] [--abandon]"` and stop.

---

## Step 1.25 — Prepare isolation before any product or state writes

Accept optional `--base REF`; remove the option/value from the task argument and preserve
its exact value in `BASE_REF` / `BASE_ARGS`. A prerequisite branch must be passed through
unchanged; never substitute main. Resolve the stable upstream task key read-only first.

```bash
WORKTREE_RECEIPT=$(bash ~/.nightshift/scripts/nightshift-worktree.sh prepare "$TASK_KEY" \
  --project "$PROJECT" "${BASE_ARGS[@]}") || exit 1
PROJECT=$(printf '%s\n' "$WORKTREE_RECEIPT" | jq -er '.worktree') || exit 1
cd "$PROJECT" || exit 1
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --project "$PROJECT" --shell) || exit $?
eval "$PROJECT_CONTEXT"
export NIGHTSHIFT_PREPARED_TASK="$TASK_KEY"
export NIGHTSHIFT_WORKTREE_RECEIPT="$WORKTREE_RECEIPT"
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK_KEY" --create)
DOCS_DIR="$PROJECT/docs"
```

Only now create sentinels, trackers, or product artifacts. Record the receipt path, branch,
base SHA, and dependency in the task tracker once created. A failed isolation gate stops
this ticket; the batch continues. For an already prepared in-progress context, use the
matching-context validation in nightshift-implement's isolation entry instead of repeating
clean-only prepare. Do not accept a task environment marker without validating its receipt.

---

## Step 1.5 — Abandon (explicit cancel + teardown)

If `--abandon` was passed, tear down the in-flight run for `$TASK_KEY` and stop — no stages
run. Abandon only applies to an already-resolved task key; a fresh source-prefixed ref has
nothing to abandon. Everything here is local — scope is thawed, the tracker is released, and
the ACTIVE marker is retired. Nothing is emitted anywhere.

```bash
if [ "$ABANDON" = "1" ]; then
  if [ "$ROUTE_FRESH" = "1" ] || [ -z "$TASK_KEY" ]; then
    echo "ORCHESTRATOR_BLOCKED: --abandon needs an existing task key (e.g. /nightshift-eng MVP-1 --abandon)."
    exit 1
  fi

  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  TRACKER="${TASK_DIR}/${TASK_KEY}.md"

  # 1. Retire the ACTIVE-* marker(s) for this ticket FIRST — it is the authoritative
  #    "a run is live" signal. Removing it before the other steps makes the teardown
  #    crash-consistent: if we die partway, the leftover scope file has no live ticket,
  #    so nightshift-crash-check reports STALE_SCOPE (a self-heal prompt) on the next run
  #    rather than leaving a silent orphan.
  for A in "${TASK_DIR}"/ACTIVE-*; do
    [ -f "$A" ] || continue
    if grep -q "^NIGHTSHIFT_TICKET=${TASK_KEY}$" "$A" 2>/dev/null; then
      rm -f "$A"
    fi
  done

  # 2. Retire matching ownership, retaining the worktree and every file.
  bash ~/.nightshift/scripts/nightshift-worktree.sh finish "$TASK_KEY" --project "$PROJECT" || exit 1

  # 3. Release the Stop hook: rewrite any ⏳ in-progress row to 🚫 abandoned.
  if [ -f "$TRACKER" ]; then
    sed -i '' "s|^⏳ \(.*\)|🚫 \1 — abandoned ${TS}|" "$TRACKER" 2>/dev/null \
      || sed -i "s|^⏳ \(.*\)|🚫 \1 — abandoned ${TS}|" "$TRACKER" 2>/dev/null || true
  fi

  # 4. Clear one-shot sentinels if any were left behind.
  rm -f "${TASK_DIR}/.invoked-by-eng" "${TASK_DIR}/.last-task-key"

  # 5. Local ledger note (soft — never fails the teardown).
  BD_ID_FILE="${DOCS_DIR}/${TASK_KEY}/.bd-id"
  [ -f "$BD_ID_FILE" ] && bd note "$(cat "$BD_ID_FILE")" \
    "nightshift-eng: run abandoned ${TS} (scope thawed, tracker released)" >/dev/null 2>&1 || true

  echo "NIGHTSHIFT_ABANDONED: ${TASK_KEY} — scope thawed, tracker released, ACTIVE marker cleared."
  echo "  Re-enter any time with: /nightshift-eng ${TASK_KEY}   (resumes at the first ⬜/❌ stage)"
  exit 0
fi
```

---

## Step 2 — Stage 1: nightshift-product (skip if resuming)

If `ROUTE_FRESH=1`, write the `.invoked-by-eng` sentinel so nightshift-product knows not to
double-orchestrate at its handoff, then invoke `/nightshift-product $REF` and wait for completion:

```bash
touch "${TASK_DIR}/.invoked-by-eng"
```

Invoke `/nightshift-product $REF`. After it returns, clean up the sentinel and read the task key
from the marker nightshift-product writes:

```bash
rm -f "${TASK_DIR}/.invoked-by-eng"
if [ -f "${TASK_DIR}/.last-task-key" ]; then
  PRODUCT_TASK_KEY=$(cat "${TASK_DIR}/.last-task-key")
  [ "$PRODUCT_TASK_KEY" = "$TASK_KEY" ] || { echo "Product task key differs from isolated ownership" >&2; exit 1; }
  rm -f "${TASK_DIR}/.last-task-key"
else
  echo "ORCHESTRATOR_BLOCKED: nightshift-product did not write .last-task-key — likely canceled."
  exit 1
fi
echo "TASK_KEY: $TASK_KEY"
```

---

## Step 3 — Stage gating — read current state from tracker

For adversarial verification, use the persisted `.adversarial-budget.json` in the
task output directory for retry admission. Infrastructure failures are not
substantive spec-repair attempts; do not exhaust the substantive gate budget by
counting failed model launches. Retain both counters and the independent total
ceiling across resumes. Other stages retain their existing budgets. Never reset
or delete budget evidence to resume a failed gate.

```bash
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK_KEY" --create)
TRACKER="${TASK_DIR}/${TASK_KEY}.md"
SPEC="${PROJECT}/docs/${TASK_KEY}/SPEC.md"
BD_ID_FILE="${PROJECT}/docs/${TASK_KEY}/.bd-id"
BD_ID=$([ -f "$BD_ID_FILE" ] && cat "$BD_ID_FILE" || echo "")

if [ ! -f "$TRACKER" ]; then
  echo "ORCHESTRATOR_BLOCKED: no tracker at $TRACKER. Did nightshift-product complete?"
  exit 1
fi
echo "BD_ID:   $BD_ID  (used for bd note/close calls)"

# Crash recovery — surface orphaned state from a prior killed session.
bash ~/.nightshift/scripts/nightshift-crash-check.sh
```

Crash reports are diagnostic. Preserve leases and scopes on interruption; never unconditionally
thaw them. Resume only a validated matching prepared context. A collision identifies the
owning task/tracker and stops this ticket for reconciliation without releasing another owner.

Determine resume point: scan `$TRACKER` for the first line in the Pipeline Stages section
starting with `⬜` (pending), `⏳` (in-progress), or `❌` (blocked). That's where we resume.
Override with `--from $FROM_STAGE` if set.

If `FROM_STAGE` is set, mark all stages that precede it as `🚫 skipped` in the tracker now:

```bash
if [ -n "$FROM_STAGE" ]; then
  STAGE_ORDER="adversarial implement review drift qa preflight deploy"
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  for s in $STAGE_ORDER; do
    [ "$s" = "$FROM_STAGE" ] && break
    case "$s" in
      adversarial) sed -i '' "s|^⬜ /nightshift-adversarial.*|🚫 /nightshift-adversarial — claim verification [skipped, $TS]|" "$TRACKER" ;;
      implement)   sed -i '' "s|^⬜ /nightshift-implement.*|🚫 /nightshift-implement — build [skipped, $TS]|" "$TRACKER" ;;
      review)      sed -i '' "s|^⬜ /nightshift-review.*|🚫 /nightshift-review — code review [skipped, $TS]|" "$TRACKER" ;;
      drift)       sed -i '' "s|^⬜ /nightshift-drift.*|🚫 /nightshift-drift — drift check [skipped, $TS]|" "$TRACKER" ;;
      qa)          sed -i '' "s|^⬜ /nightshift-qa.*|🚫 /nightshift-qa — behavioral QA [skipped, $TS]|" "$TRACKER" ;;
      preflight)   sed -i '' "s|^⬜ /nightshift-preflight.*|🚫 /nightshift-preflight — pre-deploy checklist [skipped, $TS]|" "$TRACKER" ;;
      deploy)      sed -i '' "s|^⬜ /nightshift-deploy.*|🚫 /nightshift-deploy — ship [skipped, $TS]|" "$TRACKER" ;;
    esac
  done
fi
```

Stage labels and corresponding skills:
| Tracker line begins with… | Skill to run |
|---|---|
| `/nightshift-adversarial` | `/nightshift-adversarial $TASK_KEY` |
| `/nightshift-implement` | `/nightshift-implement $TASK_KEY` (TDD locks + scope-freeze active) |
| `/nightshift-review` | `/nightshift-review $TASK_KEY` |
| `/nightshift-drift` | `/nightshift-drift $TASK_KEY` |
| `/nightshift-qa` | `/nightshift-qa $TASK_KEY` |
| `/nightshift-preflight` | `/nightshift-preflight $TASK_KEY` |
| `/nightshift-deploy` | `/nightshift-deploy $TASK_KEY` |

---

## Step 4 — Stage 2: nightshift-adversarial

```bash
sed -i '' "s|^⬜ /nightshift-adversarial.*|⏳ /nightshift-adversarial — claim verification|" "$TRACKER"
```

Invoke `/nightshift-adversarial $TASK_KEY`. Wait for completion.

If it returns `ADVERSARIAL_BLOCKED` or `ADVERSARIAL GATE: BLOCKED`: mark blocked and stop.

```bash
sed -i '' "s|^⏳ /nightshift-adversarial.*|❌ /nightshift-adversarial — claim verification [BLOCKED]|" "$TRACKER"
```

Engineer must address blocked claims before re-running.

If `ADVERSARIAL GATE: APPROVED`:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-adversarial.*|✅ /nightshift-adversarial — claim verification (APPROVED) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ adversarial → implement | compact-safe"
```

Append to `$TRACKER` under `## Decisions Made`:
```
- Adversarial APPROVED at <timestamp>. <N> overrides logged.
```

---

## Step 5 — Stage 3: /nightshift-implement with scope-freeze active

`/nightshift-implement` is the TDD-aware build stage: it spec-locks `SPEC.md`, runs the RED phase
under the agent firewall, red-locks the failing tests, detects already-fixed-upstream, then
writes the GREEN diff — all under the scope-freeze this step activates. The spec-lock + digest
regeneration happen **inside** nightshift-implement (Step 0.5), so this orchestrator only builds the
scope and invokes it. (The standalone `/implement` is untouched and remains available outside
the pipeline — nightshift-eng uses `/nightshift-implement` for the TDD locks.)

Activate from the actual Files to Change table through the checkout-local lease helper:

```bash
bash ~/.nightshift/scripts/nightshift-scope-activate.sh "$TASK_KEY" \
  --project "$PROJECT" --spec "$SPEC" || exit 1
```

Do not write scope files directly or install an unconditional thaw trap. The lease remains
until matching retain-only finish; malformed scope and another owner fail this ticket before
implementation. Scope enforcement keeps its existing union semantics.

```bash
sed -i '' "s|^⬜ /nightshift-implement.*|⏳ /nightshift-implement — build|" "$TRACKER"
```

Invoke `/nightshift-implement $TASK_KEY`. The PreToolUse hook on Edit/Write will enforce scope. If
this orchestrator is running under `AUTONOMOUS=true` (set by `/nightshift-batch`), that env is
inherited by the stage, which takes its non-interactive path and returns the JSON status
contract; read `status` to decide the branch below instead of interpreting prose.

If `/nightshift-implement` fails or is interrupted (`status:"FAIL"`, or a `## AGENT BLOCKED`): the
lease and scope remain for safe reconciliation. Mark blocked and stop after the existing repair budget.

```bash
sed -i '' "s|^⏳ /nightshift-implement.*|❌ /nightshift-implement — build [FAILED]|" "$TRACKER"
```

Re-run `/nightshift-eng $TASK_KEY` to retry from `/nightshift-implement` (Step 5). A `status:"SKIP"`
(already-fixed-upstream) is **not** a failure — mark the stage skipped and stop the pipeline
cleanly; there is nothing to review or ship.

If `/nightshift-implement` returns successfully (`status:"SUCCESS"` or prose completion):
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-implement.*|✅ /nightshift-implement — build (complete) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ implement → review | compact-safe"
```

Append to `## Decisions Made`:
```
- Implementation completed at <timestamp>. Files changed: <list from git diff>.
```

---

## Step 6 — Stage 4: nightshift-review

```bash
sed -i '' "s|^⬜ /nightshift-review.*|⏳ /nightshift-review — code review|" "$TRACKER"
```

Invoke `/nightshift-review $TASK_KEY`. Wait.

If `NIGHTSHIFT-REVIEW GATE: REQUEST CHANGES`: mark blocked and stop.

```bash
sed -i '' "s|^⏳ /nightshift-review.*|❌ /nightshift-review — code review [BLOCKED]|" "$TRACKER"
```

Engineer addresses BLOCKs (or downgrades them with reasoning), then re-runs `/nightshift-eng $TASK_KEY`.

If `APPROVE`:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-review.*|✅ /nightshift-review — code review (APPROVE) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ review → drift | compact-safe"
```

Append summary line to `## Decisions Made`. Continue.

---

## Step 7 — Stage 5: nightshift-drift

```bash
sed -i '' "s|^⬜ /nightshift-drift.*|⏳ /nightshift-drift — drift check|" "$TRACKER"
```

Invoke `/nightshift-drift $TASK_KEY`. Wait.

If `NIGHTSHIFT-DRIFT GATE: REQUEST CHANGES`: mark blocked and stop.

```bash
sed -i '' "s|^⏳ /nightshift-drift.*|❌ /nightshift-drift — drift check [BLOCKED]|" "$TRACKER"
```

Engineer either updates the spec to match reality or extends the implementation, then re-runs.

If `APPROVE`:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-drift.*|✅ /nightshift-drift — drift check (APPROVE) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ drift → qa | compact-safe"
```

Append summary. Continue.

---

## Step 7.5 — Stage 5.5: nightshift-qa

```bash
sed -i '' "s|^⬜ /nightshift-qa.*|⏳ /nightshift-qa — behavioral QA|" "$TRACKER"
```

Invoke `/nightshift-qa $TASK_KEY`. Wait. This runs the project's full Playwright suite as a
regression gate; on a project without Playwright it returns `APPROVE (no Playwright — skipped)`
at zero cost.

If `NIGHTSHIFT-QA GATE: REQUEST CHANGES`: mark blocked and stop.

```bash
sed -i '' "s|^⏳ /nightshift-qa.*|❌ /nightshift-qa — behavioral QA [BLOCKED]|" "$TRACKER"
```

Engineer fixes the regression (or re-seals tests if a locked spec changed intentionally), then
re-runs `/nightshift-eng $TASK_KEY`.

If `APPROVE` (PASS or SKIPPED):

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-qa.*|✅ /nightshift-qa — behavioral QA (APPROVE) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ qa → preflight | compact-safe"
```

Append summary. Continue.

---

## Step 8 — Stage 6: /nightshift-preflight

```bash
sed -i '' "s|^⬜ /nightshift-preflight.*|⏳ /nightshift-preflight — pre-deploy checklist|" "$TRACKER"
```

Invoke `/nightshift-preflight $TASK_KEY`. This runs the structured pre-deploy interview and writes
`docs/$TASK_KEY/PREFLIGHT.md`.

If preflight is canceled or PREFLIGHT.md not written: mark blocked and stop.

```bash
sed -i '' "s|^⏳ /nightshift-preflight.*|❌ /nightshift-preflight — pre-deploy checklist [CANCELED]|" "$TRACKER"
```

Otherwise:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-preflight.*|✅ /nightshift-preflight — pre-deploy checklist (complete) [$TS]|" "$TRACKER"
echo "══ NIGHTSHIFT-ENG STAGE BOUNDARY ══ preflight → deploy | DO NOT compact — deploy needs fresh diff"
```

Append to `## Decisions Made`.

---

## Step 9 — Stage 7: nightshift-deploy

```bash
sed -i '' "s|^⬜ /nightshift-deploy.*|⏳ /nightshift-deploy — ship|" "$TRACKER"
```

Invoke `/nightshift-deploy $TASK_KEY`. This is the irreversible one — it pushes, opens a PR,
asks the engineer to merge, then verifies via HTTP health check.

If any sub-step fails: stop. Nightshift-deploy itself surfaces the failure.

```bash
sed -i '' "s|^⏳ /nightshift-deploy.*|❌ /nightshift-deploy — ship [FAILED]|" "$TRACKER"
```

If deploy succeeds: bead is closed, PR merged. Pipeline complete.

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sed -i '' "s|^⏳ /nightshift-deploy.*|✅ /nightshift-deploy — ship (complete) [$TS]|" "$TRACKER"
```

---

## Step 10 — Retain completion and final summary

```bash
bash ~/.nightshift/scripts/nightshift-worktree.sh finish "$TASK_KEY" --project "$PROJECT" || exit 1
```

Finish retires only matching lease/scope metadata and retains all worktree files, commits,
and branches. Use the same finish call for a terminal skip. An interrupted/failed run keeps
its ownership for reconciliation; never remove another task's state.


Print:
```
══════════════════════════════════════════════════════════════════
PIPELINE COMPLETE — <task-key>

Ticket:   <external_ref>
Spec:     docs/<task-key>/SPEC.md
Review:   docs/<task-key>/REVIEW.md   (BLOCK 0, WARN <n>, NOTE <n>)
Drift:    docs/<task-key>/DRIFT.md    (BLOCK 0, WARN <n>)
Preflight: docs/<task-key>/PREFLIGHT.md
Deploy:   docs/<task-key>/DEPLOY.md
PR:       <pr_url>
Bead:     closed

Tracker:  .nightshift/<task-key>.md (or legacy task home)
══════════════════════════════════════════════════════════════════
```

Append to tracker `## Decisions Made`:
```
- Pipeline complete at <timestamp>. Shipped via <pr_url>.
```

Update `## Remaining Work` to: `(none)`.

---

## Resume semantics

Re-running `/nightshift-eng <task-key>` mid-pipeline is safe:

- Reads `$TRACKER`, finds the first unchecked stage, resumes there.
- Each stage skill is idempotent: re-running nightshift-review just regenerates REVIEW.md and
  appends a new trend log entry; re-running nightshift-adversarial offers resume-or-fresh.
- Scope activation is atomic and checkout-local. Matching finish retires ownership;
  interruption retains it. Never clear another ticket's lease or scope on resume.
