---
name: nightshift-product
description: "Spec Production Harness — fetches a ticket from any source (gh/jira/monday/notion/bd), mirrors it into beads as the local engineering ledger, asks three grounding questions, runs nightshift-code-fact-extractor on identifiers, then delegates to /nightshift-spec with Sources + Model Router enforcement. The upstream ticket id (e.g., MVP-1) is the canonical task key for everything downstream; the bead id is saved internally in docs/<task-key>/.bd-id. Run /nightshift-product <REF> to start."
argument-hint: "<REF> — gh:123 | jira:KEY-1 | monday:1234 | notion:<id> | bd:bd-abc | bare-bd-id"
---

# /nightshift-product — Spec Production Harness

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

Bootstraps a guarded spec-production session for any ticket. Resolves the source-of-truth
ticket via a pluggable adapter, mirrors it into **beads** as the local engineering ledger,
asks three grounding questions, then delegates to `/nightshift-spec`. The `spec-guardrail` hook enforces
the output — no spec ships without verified `## Sources` and a filled `## Model Router`.

**Why this exists:** Without a harness, the spec-writer receives a pre-digested brief and
skips verification — writing facts from assumptions rather than confirmed code. Grounding
questions anchor the brief to what the engineer actually intends to build.

**Hard rules:**
- **Source-of-truth = the upstream ticket** (Monday/Jira/GH/Notion as configured per project).
- **Local engineering ledger = beads.** Every run mirrors into beads via `--external-ref` so
  beads stays in lockstep with upstream without becoming a competing SSOT.
- **Canonical task key = the upstream ticket id** (e.g., `MVP-1`, `12`, the Monday item id).
  Spec lives at `docs/<task-key>/SPEC.md`. The bead id is recorded in `docs/<task-key>/.bd-id`
  for bd ops downstream — it's an internal implementation detail, not a user-facing key.
  When the source IS beads (no upstream ticket), the bead id IS the task key.
- **No gstack.** Do not invoke `/ship`, `/land-and-deploy`, `/health`, `/review` (gstack),
  `/canary`, `/qa`, `/design-review`, or any other gstack-namespaced skill from this harness.
  The nightshift-* pipeline is independent.

---

## Usage

```
/nightshift-product gh:12              — fetch GH Issue #12 in the current repo
/nightshift-product gh:owner/repo#12   — fetch GH Issue #12 in owner/repo
/nightshift-product jira:MVP-1         — fetch Jira issue MVP-1
/nightshift-product monday:1234567890  — fetch Monday item by id
/nightshift-product notion:<page-id>   — fetch Notion page
/nightshift-product bd:bd-abc123       — work directly off an existing bead
/nightshift-product bd-abc123          — bare bead id (no prefix needed)
/nightshift-product stop               — clean up tracker state for current active task
```

---

## Step 1 — Parse argument

Read `$ARGUMENTS`. Trim whitespace.

If empty, print usage and stop:
> "Usage: /nightshift-product <REF> — fetches a ticket and starts a guarded spec session. See description for ref formats."

If `$ARGUMENTS` is `stop` → jump to **Stop Flow** at the bottom.

Otherwise treat as `<REF>` and proceed.

---

## Step 2 — Resolve paths and fetch ticket

```bash
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "$ARGUMENTS") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
REF=$(jq -r '.arguments' <<< "$STAGE_ARGS")
TICKET_JSON=$(~/.nightshift/scripts/nightshift-ticket-source.sh "$REF" 2>&1)
# Use `printf '%s'` (not `echo`) when re-piping captured JSON — on shells
# where echo interprets backslash escapes (the agent's calling shell does),
# `\n` inside string values gets converted to a literal newline and breaks
# parsing. printf %s is escape-safe.
if ! printf '%s' "$TICKET_JSON" | jq empty 2>/dev/null; then
  echo "TICKET_FETCH_FAILED:"
  echo "$TICKET_JSON"
  exit 1
fi
printf '%s\n' "$TICKET_JSON" | jq .
```

If the fetch failed, surface the error JSON to the user and stop. Common causes:
- Wrong prefix (`gh:` vs `jira:`)
- Missing env vars (`JIRA_TOKEN`, `MONDAY_TOKEN`, `NOTION_TOKEN`)
- Issue id does not exist in the source

---

## Step 3 — Mirror to beads (local engineering ledger)

Beads is **optional**. It is the local engineering ledger, never the source of truth, so its
absence degrades the pipeline rather than stopping it: no bead id, no `bd note` breadcrumbs,
everything else unchanged.

```bash
BD_ID=""
if bash ~/.nightshift/scripts/nightshift-capability.sh --has bd; then
  BD_ID=$(printf '%s' "$TICKET_JSON" | ~/.nightshift/scripts/nightshift-beads-mirror.sh)
  if [ -z "$BD_ID" ]; then
    echo "BEADS_MIRROR_FAILED — see stderr above."
    exit 1
  fi
  echo "BEAD: $BD_ID (internal — used for bd ops only)"
else
  echo "BEADS_UNAVAILABLE — bd not installed; continuing without the local ledger."
fi

# Canonical task key = upstream ticket id (source_id). Falls back to bead id
# when the source IS beads (no upstream ticket to mirror).
SOURCE=$(printf    '%s' "$TICKET_JSON" | jq -r '.source')
SOURCE_ID=$(printf '%s' "$TICKET_JSON" | jq -r '.source_id')
if [ "$SOURCE" = "bd" ]; then
  # Source IS beads — bd is required for this ref shape, so a missing BD_ID is fatal here only.
  if [ -z "$BD_ID" ]; then
    echo "A bd:* ref requires beads, but bd is not installed. Use a gh:/jira:/monday:/notion: ref instead."
    exit 1
  fi
  TASK_KEY="$BD_ID"
else
  TASK_KEY="$SOURCE_ID"
fi

TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK_KEY" --create)
TRACKER="${TASK_DIR}/${TASK_KEY}.md"
SPEC_DIR="${PROJECT}/docs/${TASK_KEY}"
SPEC="${SPEC_DIR}/SPEC.md"

mkdir -p "$TASK_DIR" "$SPEC_DIR"

# Persist the bead id alongside the spec so downstream stages can run bd ops
# without re-resolving from upstream.
echo "$BD_ID" > "${SPEC_DIR}/.bd-id"

# Persist the task key for /nightshift-eng to pick up after this command returns.
echo "$TASK_KEY" > "${TASK_DIR}/.last-task-key"

echo "PROJECT:  $PROJECT"
echo "TASK_KEY: $TASK_KEY  (visible folder/tracker name)"
echo "BEAD_ID:  $BD_ID    (internal; saved to ${SPEC_DIR}/.bd-id)"
echo "SPEC:     $SPEC"
echo "TRACKER:  $TRACKER"
```

Display a short summary of the resolved ticket:

```
──────────────────────────────────────────────────────────────
TICKET:   <external_ref>  →  bead <task-key>
Title:    <title>
Source:   <source> (state: <state>)
URL:      <url>
Labels:   <labels>
──────────────────────────────────────────────────────────────
```

Ask: **"Is this the right ticket? (yes / no)"**

- **No** → "Stopping. Re-run `/nightshift-product <correct-ref>`." and exit. (Do not delete the bead — it's a local mirror; harmless.)
- **Yes** → continue.

---

## Step 3.5 — Optional product-spec airlock

Check if `$ARGUMENTS` contains `--override`. If so, skip this step entirely and set
`PRODUCT_SPEC_REF=OVERRIDE`.

Otherwise, ask the engineer:
> "Do you have a product spec or PRD for this ticket? Paste a Confluence URL, a local file
> path, or type `skip` to bypass."

Handle the response:

- **Valid Confluence URL** (contains `atlassian.net` or `/wiki/`) — call `mcp__claude_ai_Atlassian__getConfluencePage` with the URL. If successful, set `PRODUCT_SPEC_CONTENT` and `PRODUCT_SPEC_REF` from the result. If the fetch fails (auth, 404), warn and set `PRODUCT_SPEC_CONTENT=` (empty) with a note.
- **Local file path** — if the file exists, read it and set `PRODUCT_SPEC_CONTENT` and `PRODUCT_SPEC_REF` to the path.
- **`skip` or empty after one retry** — set `PRODUCT_SPEC_REF=OVERRIDE`. Print: `⚠  Proceeding without product spec.`

Persist the airlock result to the per-ticket ACTIVE file (written in Step 8):
```bash
PRODUCT_SPEC_REF="${PRODUCT_SPEC_REF:-OVERRIDE}"
```

If override was invoked, inject this warning verbatim into the spec-writer delegation (Step 7):
```
> ⚠️ **AIRLOCK BYPASSED** — This spec was produced without a linked product spec.
> Product sign-off is missing. Ticket: <TASK_KEY> | Date: <today>
```

---

## Step 4 — Check for existing spec

```bash
if [ -f "$SPEC" ]; then
  echo "SPEC_EXISTS: $SPEC"
fi
```

If a spec already exists, ask:
> "A spec already exists for `$TASK_KEY`. Use it or regenerate? (use / regen)"

- **use** → skip to Step 8 (handoff).
- **regen** → continue to Step 5.

---

## Step 5 — Three grounding questions

Ask one at a time. Wait for each answer before asking the next.

1. **Intent check:** "In one sentence — what is this ticket actually building? (Ticket titles drift from real intent — this anchors the spec.)"

2. **Hidden constraints:** "Any constraints the ticket doesn't mention? (Performance requirements, backwards-compat, demo time limits, related in-progress work.)"

3. **Blast radius:** "Are there other files or features likely to be affected beyond what the ticket calls out? List them or say none."

---

## Step 6 — Invoke nightshift-code-fact-extractor on all identifiers

Before delegating to spec-writer, extract all technical identifiers from the ticket body and
grounding answers — function names, hook names, type names, file paths, API routes, component
names, CSS tokens — and write the full list and grounding context to
`docs/$TASK_KEY/product-extractor.in.md`. Use the bounded transport fallback below.
It owns all three attempts for this extraction; do not wrap it in another retry
loop. It escalates only missing local runtime/model, connection refusal, or capacity
failures. Authentication, schema, policy, and semantic failures stop for the
existing repair policy. A manual gear override uses one dispatcher invocation.

```bash
DISPATCH="${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-agent.sh"
EXTRACT_ARGS=(--gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --attempt "${GATE_ATTEMPT:-1}")
if [ "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" = auto ]; then
  DISPATCH="${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-dispatch-bounded.sh"
  EXTRACT_ARGS=()
fi
if bash "$DISPATCH" nightshift-code-fact-extractor "${EXTRACT_ARGS[@]}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-low}" \
  --in "docs/$TASK_KEY/product-extractor.in.md" --out "docs/$TASK_KEY/product-extractor.out.json"; then
  jq '.results.claims' "docs/$TASK_KEY/product-extractor.out.json"
else
  jq '{status,reason}' "docs/$TASK_KEY/product-extractor.out.json"
  # Apply the existing failure policy; do not advance to spec writing.
fi
```

Require SUCCESS and a complete claim per submitted identifier. Map VERIFIED to
FOUND_MATCH, CONFLICT to FOUND_CONFLICT, and NOT_FOUND to the existing missing/new
identifier evidence policy. Preserve each claim's file, line and inspected_files;
status alone never proves an identifier. SKIP is not completed extraction.

This step is mandatory. Do not send a spec-writer brief until extractor results are in hand.

Print: `"Extracted N identifiers. Running nightshift-code-fact-extractor..."`

Capture the UTC start time before invoking the extractor:
```bash
EXTRACTOR_RUN=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Pass `EXTRACTOR_RUN` to the spec-writer delegation in Step 7. Every citation JSONL entry
written during adversarial verification MUST include `"extractor_run": "$EXTRACTOR_RUN"` —
this timestamp enables drift detection between spec-write time and adversarial-run time.

**Optional structural grounding via graphify:** If `graphify` is on PATH, also run
`graphify "$PROJECT" --quiet` and pass the resulting `graphify-out/graph.json` path to the
spec-writer as supplementary context. This gives the spec-writer a real call-graph and
file-relationship map to ground claims against, on top of the per-identifier extractor results.
Skip silently if graphify is not installed — it's an enhancement, not a requirement.

### 6b — Populate the shared claim cache

After the extractor returns, write each clean result (`FOUND_MATCH` or `NET_NEW` — no
conflicts) to the shared cache `$TASK_DIR/.claim-cache.jsonl` via
`~/.nightshift/scripts/nightshift-claim-cache.sh`. The cache key is computed from
`(identifier_text, $HEAD_SHA, sorted(file_targets))` — for /nightshift-product, `file_targets`
are the files the extractor inspected (the ticket has no `## Files to Change` table yet;
the upcoming spec will). This pre-populates the cache so /nightshift-adversarial gets hits on
overlapping identifiers in the spec's claims.

```bash
HEAD_SHA=$(git rev-parse HEAD)
# For each clean extractor result, build a record and append.
# See scripts/nightshift-claim-cache.sh hash/append for the contract.
```

Conflict or ambiguous extractor results are written to the spec-writer brief as-is but
**not** cached — /nightshift-adversarial will re-verify them against the eventual spec where
`file_targets` is authoritative.

---

## Step 7 — Delegate to /nightshift-spec

Prepare `docs/$TASK_KEY/spec-writer.in.md` with all the items below and invoke
`/nightshift-spec $TASK_KEY`, whose Step 3 uses this exact file protocol:

```bash
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-agent.sh" \
  nightshift-spec-writer --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --in "docs/$TASK_KEY/spec-writer.in.md" \
  --out "docs/$TASK_KEY/spec-writer.out.json"; then
  jq '{status,reason,results,artifacts}' "docs/$TASK_KEY/spec-writer.out.json"
else
  jq '{status,reason}' "docs/$TASK_KEY/spec-writer.out.json"
  # Preserve the writer failure/block policy; do not advance.
fi
```

The standalone stage performs the invocation once; do not dispatch a second writer.
After SUCCESS, persist `.artifacts.provider` from this normalized output as
`docs/$TASK_KEY/spec-author-provider.txt`. Require the returned `.results.spec_path`
to identify the actual spec and verify its existence and source evidence before
advancing. Codex/local routes are read-only: a separate authorized integration is
required to write a spec; absence of the artifact is a failed stage.

**Ticket content:** the resolved ticket title + body verbatim (from Step 2 JSON).

**Beads metadata:** `bd_id`, `external_ref`, source URL.

**Engineer Notes (from Step 5):**
```
Intent: <Q1>
Hidden constraints: <Q2>
Blast radius: <Q3>
```

**Product spec context (from Step 3.5):** if `PRODUCT_SPEC_CONTENT` is non-empty, include it
verbatim under a `## Product Spec` heading in the delegation brief. If `PRODUCT_SPEC_REF=OVERRIDE`,
inject the airlock bypass warning at the top of the spec-writer brief.

**Extractor results (from Step 6):** the full verification manifest, plus optional graphify
graph.json path if it ran. Include `EXTRACTOR_RUN` timestamp so the spec-writer can embed it
in the `## Sources` section preamble.

**Required spec output — inject verbatim into the spec-writer delegation:**

> **REQUIRED — every spec must include these two final sections:**
>
> ### ## Model Router
> Count the Files to Change table. Apply the decision tree:
> - ≥ 3 files OR ≥ 2 top-level modules → **Opus / Enterprise Architect**
> - Architecture or design decision? → **Opus**
> - Shared contract change (API, DTO, hook signature)? → **Opus**
> - Otherwise → **Sonnet / General Engineer**
>
> Write the decision as a filled line: `**Decision:** Sonnet / General Engineer`
> A bracket placeholder `[ ]` will be blocked by the spec-guardrail hook.
>
> ### ## Sources
> List every file read to support a factual claim. Format per entry:
> `` `repo-relative/path/to/file.ext:LINE_START-LINE_END` (branch: BRANCH, commit: SHORT_SHA) — what this confirms ``
> Line numbers required. Branch required. Commit SHA (`git rev-parse --short HEAD`) required.
> Vague entries ("see file") are invalid. The spec-guardrail hook blocks the Write if Sources
> is absent or has no `path:line ... commit:` entries.

Spec saves to `docs/<task-key>/SPEC.md`.

---

## Step 8 — Write process tracker and update beads

After the spec is approved:

```bash
TODAY=$(date +%Y-%m-%d)
INIT_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EXT_REF=$(printf      '%s' "$TICKET_JSON" | jq -r '.external_ref')
TICKET_TITLE=$(printf '%s' "$TICKET_JSON" | jq -r '.title')
TICKET_URL=$(printf   '%s' "$TICKET_JSON" | jq -r '.url // ""')

cat > "$TRACKER" << EOF
# ${TASK_KEY} — nightshift-* Pipeline Tracker

**Started:** ${TODAY}
**Ticket:** ${EXT_REF} — ${TICKET_TITLE}
**URL:** ${TICKET_URL}
**Spec:** docs/${TASK_KEY}/SPEC.md
**Status:** Spec approved

## Pipeline Stages
✅ Ticket fetched and mirrored to bead
✅ Grounding questions answered
✅ nightshift-code-fact-extractor run
✅ Spec approved
⬜ /nightshift-adversarial — claim verification
⬜ /nightshift-implement — build (TDD locks)
⬜ /nightshift-review — DRY/SOLID/ACID/CoC/BigO/LLM-trust
⬜ /nightshift-drift — spec ↔ diff drift check
⬜ /nightshift-qa — behavioral QA (Playwright)
⬜ /nightshift-preflight — pre-deploy checklist
⬜ /nightshift-deploy — ship

## Decisions Made
(Decisions accumulate here as each stage runs.)

## Remaining Work
(Updated after each stage.)

## Init time: ${INIT_TIME}
EOF
echo "Tracker written: $TRACKER"

# Write per-ticket ACTIVE file so downstream commands can pick up context
ACTIVE="${TASK_DIR}/ACTIVE-${TASK_KEY}"
cat > "$ACTIVE" << EOF
NIGHTSHIFT_TICKET=${TASK_KEY}
NIGHTSHIFT_PHASE=adversarial
NIGHTSHIFT_INIT_TIME=${INIT_TIME}
NIGHTSHIFT_EXT_REF=${EXT_REF}
NIGHTSHIFT_PRODUCT_SPEC_REF=${PRODUCT_SPEC_REF:-NONE}
EOF
echo "ACTIVE file written: $ACTIVE"
```

Append a note to the bead linking the spec:

```bash
[ -n "$BD_ID" ] && bd note "$BD_ID" "Spec generated: docs/${TASK_KEY}/SPEC.md

Run /nightshift-adversarial ${TASK_KEY} for claim verification, then /nightshift-implement ${TASK_KEY} to build.
Or run /nightshift-eng ${TASK_KEY} to orchestrate the whole pipeline." 2>/dev/null || true
```

---

## Step 9 — Handoff

Print:

> "Spec approved and saved to `docs/<task-key>/SPEC.md`. Bead `<task-key>` updated with spec link."

### 9a — Auto-continue into /nightshift-eng when standalone

If nightshift-product was invoked by `/nightshift-eng` itself, a sentinel file `.invoked-by-eng` will
exist in `$TASK_DIR`. In that case nightshift-eng will resume on its own — print the next-steps
hint and stop:

```bash
if [ -f "${TASK_DIR}/.invoked-by-eng" ]; then
  rm -f "${TASK_DIR}/.invoked-by-eng"
  echo ""
  echo "Returning control to /nightshift-eng for adversarial → implement → review → drift → preflight → deploy."
  exit 0
fi
```

Otherwise nightshift-product was run standalone. Offer to continue into the full pipeline:

> "Spec is the first stage. Continue into `/nightshift-eng <task-key>` to run adversarial →
> implement → review → drift → preflight → deploy? (Y/n) — default Y"

Read the answer. Treat empty input, `y`, `Y`, `yes`, `YES` as **Yes**. Treat `n`, `N`, `no`,
`NO` as **No**.

- **Yes** → invoke `/nightshift-eng $TASK_KEY` now. nightshift-eng's Step 1 will resolve `$TASK_KEY` as
  an existing task folder (ROUTE_FRESH=0) and jump to Step 3, skipping its own nightshift-product
  call. The interior gates (adversarial OVERRIDE prompts, preflight interview, deploy merge
  confirm) remain — auto-continue removes the dead-end handoff, not the safety stops.
- **No** → print:
  > "Stopping after spec. Resume any time with `/nightshift-eng <task-key>` or run individual
  > stages (`/nightshift-adversarial`, `/nightshift-implement`, …) directly."
  then exit.

---

## Stop Flow

```bash
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT")
TRACKER=$(ls "${TASK_DIR}/"bd-*.md 2>/dev/null | head -1)
ACTIVE=$(ls "${TASK_DIR}/ACTIVE-"* 2>/dev/null | head -1)

echo "Harness stopped."
if [ -n "$TRACKER" ]; then
  echo "Tracker: $TRACKER"
fi
if [ -n "$ACTIVE" ]; then
  rm -f "$ACTIVE"
  echo "ACTIVE file removed: $ACTIVE"
fi
echo "Run /nightshift-product <REF> to start a new session."
```
