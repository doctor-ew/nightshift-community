---
name: nightshift-adversarial
description: "Adversarial spec verification — loads an approved spec, extracts every technical claim, runs nightshift-code-fact-extractor on each one, and surfaces conflicts to the engineer for CONFIRM/OVERRIDE/BLOCK decisions. BLOCKED if unresolved claims remain. APPROVED gates downstream. Run /nightshift-adversarial <task-key>."
argument-hint: "<task-key> — e.g., MVP-1 (matches docs/<task-key>/SPEC.md)"
---

# /nightshift-adversarial — Spec Claim Verification

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

Consumes an approved spec and adversarially verifies every technical claim before a single
line of code is written. The engineer decides each conflict — CONFIRM as written, or OVERRIDE
with explicit reasoning. BLOCKED if unresolved claims remain.

**Credible Hulk principle:** AI does all the verification legwork. The engineer carries the
receipts and makes every override call. No claim reaches the codebase without a human sign-off.

**No gstack.** Do not invoke `/review` (gstack), `/qa`, `/health`, or any other gstack skill
from this stage. Use `nightshift-code-fact-extractor` (local agent) and optionally `graphify` for
structural grounding.

---

## Step 1 — Parse argument and resolve paths

```bash
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --shell) || exit $?
eval "$PROJECT_CONTEXT"
PROJECT="$NIGHTSHIFT_PROJECT_DIR"
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "$ARGUMENTS") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
TASK=$(jq -r '.arguments' <<< "$STAGE_ARGS")
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
CITATION="${TASK_DIR}/${TASK}-citations.jsonl"

mkdir -p "$TASK_DIR" "${PROJECT}/docs/${TASK}"
```

If `$ARGUMENTS` empty: print `"Usage: /nightshift-adversarial <task-key>"` and stop.

---

## Step 2 — Verify spec exists

```bash
if [ ! -f "$SPEC" ]; then
  echo "SPEC_MISSING: $SPEC"
fi
```

If missing, ask: `"No spec found. Run /nightshift-product <ref> first to generate one. Stop."` and exit.

---

## Step 3 — Resume detection

```bash
if [ -f "$CITATION" ] && [ -s "$CITATION" ]; then
  EXISTING=$(wc -l < "$CITATION" | tr -d ' ')
  echo "CITATION_EXISTS: ${EXISTING} entries from prior run"
fi
```

If a citation file exists, ask:
> "Found N citations from a prior run. **A)** Resume (skip already-cited claims) **B)** Start fresh (delete and re-run all)"

If **B**: `rm "$CITATION"`.

---

## Step 4 — Verify the spec's ## Sources section

Dispatch all extractor calls through `scripts/nightshift-dispatch-bounded.sh` (which invokes the shared role dispatcher) with
`--author-provider` copied from the spec-writing result's `_provenance.provider`.
Do not infer authorship from the current runtime. If prior author provenance is
missing, block verification until authorship is established. Explicit adversarial
review using another role also passes `--adversarial`. Missing alternate providers
are a blocked gate, never permission for same-provider review. The dispatcher
publishes normalized JSON: `status`, `summary`, `findings`, `evidence`, and its own
`_provenance`; parse the report from these fields rather than provider event logs.
Carry this provenance into citations and the stage receipt. A failed or blocked
result cannot approve the gate, even if the provider process exited successfully.

Retry admission is persisted in the task output directory's
`.adversarial-budget.json`. Infrastructure failures do not consume substantive
spec-repair attempts: retain separate counters and the independent total-call
ceiling. Read `next_action` after any nonzero exit; never reset this file to gain
attempts. An unsupported model requires a routing configuration change before
another launch. A completed report with conflicts requires a spec repair, not a
transport retry. See `docs/RETRY-BUDGETS.md` for limits and interrupted reservations.

A zero dispatcher exit means **report available**, not gate approval. A valid
report leaves its prelaunch reservation pending until this stage evaluates it.
The dispatcher-owned `<output>.retry.json` sidecar supplies `state_path`,
`attempt_id`, and the retained `result_path`; never take these from model output.
After validating completeness, evidence and the mappings below, finalize that
same attempt using the accounting CLI. Set `EVALUATION_CATEGORY` to `success`
only for an accepted batch, `substantive` for mapped findings requiring repair,
or `schema` for an incomplete/malformed batch. `NOT_FOUND` on a spec-authored
`[NEW]` claim maps to `NET_NEW` and is not a substantive failure. A raw model
status alone does not decide the category.

Finalization recipe (`REPORT` is the just-evaluated requested output path):

```bash
python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-retry-budget.py" \
  --state "$(jq -er '.state_path' "$REPORT.retry.json")" \
  --attempt-id "$(jq -er '.attempt_id' "$REPORT.retry.json")" \
  --category "$EVALUATION_CATEGORY"
```

Read the resulting `next_action` before another invocation. Do not finalize
again with a different category; retained attempts are immutable after mapping.
Nonzero dispatcher exits already finalize infrastructure/role failures and must
not use an older sidecar. A pending reservation blocks further dispatch: finish
the recorded evaluation before retrying, without deleting its evidence.

Read `## Sources` from `$SPEC`. If absent or empty, hard-stop:

```
ADVERSARIAL_BLOCKED: Spec has no ## Sources section.
Re-run /nightshift-product to regenerate the spec with Sources enforced.
```

Parse all entries from `## Sources` into a single list — each entry has a file path,
line range, commit SHA, and description. Invoke **nightshift-code-fact-extractor** **once** with
the full source list (the agent accepts a list of identifiers/paths; passing one source
per invocation reloads the 8.5 KB extractor system prompt N times and is the dominant
cost in this stage on a citation-heavy spec).

Print before invocation: `"Verifying N source entries in one batched extractor call…"`

Write the full source list, expected line ranges, commit/branch and descriptions to
`docs/$TASK/adversarial-sources.in.md`. Obtain actual authorship from the
successful writer receipt persisted by product/spec; never infer it from runtime
or role. Missing provenance is a blocked verification until recovered from an
actual author receipt.

```bash
AUTHOR_PROVIDER=$(cat "docs/$TASK/spec-author-provider.txt")
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-dispatch-bounded.sh" \
  nightshift-code-fact-extractor --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --adversarial \
  --author-provider "$AUTHOR_PROVIDER" --in "docs/$TASK/adversarial-sources.in.md" \
  --out "docs/$TASK/adversarial-sources.out.json"; then
  jq '.results.claims' "docs/$TASK/adversarial-sources.out.json"
else
  jq '{status,reason}' "docs/$TASK/adversarial-sources.out.json"
  # Read .adversarial-budget.json; infrastructure failures do not consume spec repairs.
fi
```

Require SUCCESS and N complete entries in `.results.claims`. Map VERIFIED to
FOUND_MATCH, CONFLICT to FOUND_CONFLICT; preserve NOT_FOUND and each file, line,
claim and inspected_files. Include source drift evidence in claim text or artifact
files referenced by `.artifacts.diff`. SKIP is not successful verification.
Map per-entry result:

| Result | Action |
|--------|--------|
| File + lines + content match description | Silent `SOURCES_VERIFIED` |
| Lines off by > 5 | Surface as `SOURCES_CONFLICT` (line drift) |
| HEAD commit ≠ cited commit | Surface as `SOURCES_CONFLICT` (code changed) |
| File path missing | Surface as `SOURCES_CONFLICT` (path not found) |
| Entry missing line/branch/commit | Surface as `SOURCES_INVALID` |

If the response is malformed (cannot parse N blocks): re-issue the batch once. If the
second attempt is also malformed, hard-stop — never silently mark sources verified
from a partial parse.

For each conflict/invalid entry, present:

```
────────────────────────────────────────────────────────────────
SOURCES CHECK — `<path>:<lines>` (branch: <branch>, commit: <sha>)
Description: "<description>"
Extractor result: <what was found>

  A) CONFIRM — source is correct; extractor result is misleading
  B) NOTE DISCREPANCY — acknowledge drift; will update spec before PR
  C) BLOCK — source is wrong; spec must be corrected now
────────────────────────────────────────────────────────────────
```

Choice **C** adds to the blocked list (Step 8).

Finalize the source report using the recipe above before dispatching the claim
batch. Malformed responses finalize as `schema` before the bounded reissue;
source discrepancies requiring repair finalize as `substantive`. Only accepted
source mappings finalize as `success`. Retain all existing source gates.

---

## Step 5 — Extract claims from spec

Read the full spec. Extract all technical claims:

| Category | Examples |
|----------|---------|
| Function/method names + signatures | `useFoo`, return type |
| Type names, interfaces, enums | `Vehicle`, `Status` |
| Field/property names | `vehicles`, `isLoading` |
| File paths stated as authoritative | `src/hooks/useFoo.ts` |
| Behavioral assertions stated as fact | "returns undefined when error" |
| Constants and magic values | `"GOLD"`, `10000` |
| CSS tokens / class names | `bg-surface`, `text-error` |

Build a numbered list. One verifiable assertion per claim. Skip requirements ("should", "must").

**Tag each claim `[EXISTING]` or `[NEW]`:**
- `[EXISTING]` — should currently exist in the codebase
- `[NEW]` — spec is creating it ("create", "add", "implement")

When in doubt, tag `[EXISTING]` — over-challenging is safer than accepting a fabrication.

If resuming, skip claims whose text already appears in the citation file.

Print: `"Extracted N claims (X EXISTING, Y NEW). Beginning verification..."`

---

## Step 6 — Batched per-claim verification with durable cache

The dominant cost in /nightshift-adversarial is reloading the extractor system prompt for
every claim. Two changes collapse it:

**(a) Batch.** Invoke `nightshift-code-fact-extractor` **once** with the full claim list, not N
times. The extractor's three-tier search (exact grep → case-insensitive → type-specific
deep extraction) runs inside the single invocation.

**(b) Durable two-tier cache.** Before invoking the extractor, partition claims into
cache hits (replayed for free) and cache misses (the actual batch). The cache key is
content-addressed:

```
sha256(claim_text + git_HEAD_sha + sorted(file_targets))
```

`file_targets` are parsed from the spec's `## Files to Change` table (same parser the
scope-freeze hook uses) — they are authoritative and known up front, unlike "files the
extractor inspected" which can only be observed post-hoc.

### 6a — Build file_targets + partition claims

```bash
SCRIPT="$HOME/.nightshift/scripts/nightshift-claim-cache.sh"
SHARED_CACHE="${TASK_DIR}/.claim-cache.jsonl"
HEAD_SHA=$(git rev-parse HEAD)

# Parse Files to Change paths from the spec (same regex as nightshift-scope-freeze.sh)
FILE_TARGETS=$(grep -E '^\| `[^`]+`' "$SPEC" \
  | sed -E 's/^\| `([^`]+)`.*/\1/' \
  | jq -R . | jq -sc '.')
```

For each claim from Step 5, compute its cache key and look it up in two places, in order:

1. **Per-task citations** (`$CITATION` — the existing `<task-key>-citations.jsonl`).
   A record with a matching `cache_key` field is a hit; the existing citation is reused
   verbatim and the claim is excluded from the batch.
2. **Shared cache** (`$SHARED_CACHE`). On hit, copy the citation block into `$CITATION`
   with `"cache_origin":"shared"` and exclude from the batch.

Claims with no hit go into the extract batch.

Print: `"Verifying N claims (M cache hits, K to extract)…"`

### 6b — Invoke the batched extractor (only if K > 0)

If the extract batch is non-empty, invoke **nightshift-code-fact-extractor** once with the full
batch. The extractor's contract: return one structured result block per claim, in the
same order as the input list, including the list of files it actually inspected.

Prepare `docs/$TASK/adversarial-claims.in.md` with the complete uncached batch
and evidence requirements. Dispatch once with the same actual author provenance:

```bash
AUTHOR_PROVIDER=$(cat "docs/$TASK/spec-author-provider.txt")
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-dispatch-bounded.sh" \
  nightshift-code-fact-extractor --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --adversarial \
  --author-provider "$AUTHOR_PROVIDER" --in "docs/$TASK/adversarial-claims.in.md" \
  --out "docs/$TASK/adversarial-claims.out.json"; then
  jq '.results.claims' "docs/$TASK/adversarial-claims.out.json"
else
  jq '{status,reason}' "docs/$TASK/adversarial-claims.out.json"
  # Read .adversarial-budget.json; repair substantive findings before reissuing.
fi
```

Consume `.results.claims` only after SUCCESS and K complete ordered entries;
apply the same VERIFIED/CONFLICT/NOT_FOUND mapping as the source batch. Keep the
existing cache and citation evidence gates, including inspected files, unchanged.

**Optional graphify grounding:** if `graphify-out/graph.json` exists from
`/nightshift-product` Step 6, query it for structural relationships related to each claim
(call-graph hits, file co-location) and pass results to the extractor as supplementary
context for the whole batch.

If the batch response cannot be parsed into K complete blocks: re-issue the batch once.
If the second attempt is also malformed, hard-stop. Never silently mark claims verified
from a partial parse.

Stream per-claim results to the engineer as they parse (avoid "the model went quiet"):

```
[1/K] useFoo returns Vehicle[] — FOUND_MATCH
[2/K] RNW1 enum member — NOT_FOUND
…
```

### 6c — Result mapping

| Outcome | Condition | Action |
|---------|-----------|--------|
| `FOUND_MATCH` | Extractor confirms exactly | Silent `VERIFIED` citation; cache |
| `FOUND_CONFLICT` | Identifier found, details differ | Surface to challenge loop; **do not** cache |
| `NOT_FOUND` + `[EXISTING]` | Should exist, doesn't | Surface to challenge loop; **do not** cache |
| `NOT_FOUND` + `[NEW]` | Spec creating it | Silent `NET_NEW` citation; cache |

### 6d — Cache safety net (file_targets mismatch)

If the extractor's `inspected_files` for a claim is not a subset of `file_targets`, the
cache key understated the dependency. **Invalidate** the would-be cache entry instead
of writing it (`nightshift-claim-cache.sh invalidate <key>`) and emit a `NOTE` so the engineer
knows the spec's Files to Change table should be widened.

### 6e — Record shapes

**Silent VERIFIED** (written to `$CITATION` AND `$SHARED_CACHE` when not from cache):
```json
{"claim":"<text>","status":"VERIFIED","source":{"file":"<path>","line":N},"challenge":null,"override_reasoning":null,"risk_level":null,"cache_key":"<sha256>","cache_origin":"computed","inspected_files":["<paths>"]}
```

**Silent NET_NEW** (same dual write):
```json
{"claim":"<text>","status":"NET_NEW","source":null,"challenge":"Not in codebase — being created by this spec.","override_reasoning":null,"risk_level":null,"cache_key":"<sha256>","cache_origin":"computed","inspected_files":[]}
```

`cache_origin` values:
- `computed` — extractor just ran; written to both per-task and shared cache.
- `per-task` — replayed from `$CITATION` (a prior run on this same task).
- `shared` — replayed from `$SHARED_CACHE` (a prior run on this or another task).

Use the bundled helper for hash/lookup/append/invalidate — see `scripts/nightshift-claim-cache.sh`
in this repo (mirrored to `~/.claude/scripts/` by the installer). Never reach for a
Python SDK / `cache_control: ephemeral` workaround here — the 5-minute TTL is the wrong
cache layer for a stage that BLOCKS for hours during engineer triage, and the SDK path
breaks the interactive challenge loop in Step 7. This retained file cache remains available across the interactive challenge loop.

---

## Step 7 — Interactive challenge loop

For each `FOUND_CONFLICT` or `NOT_FOUND [EXISTING]`:

```
────────────────────────────────────────────────────────────────
CLAIM [N/total]: "<claim text>"
Extractor result: <what was found>

  A) CONFIRM as VERIFIED — extractor is misleading; claim is correct
  B) OVERRIDE — acknowledge discrepancy; will provide reasoning
  C) BLOCK — need to investigate before proceeding
────────────────────────────────────────────────────────────────
```

**Choice A — CONFIRM:**
```json
{"claim":"<text>","status":"VERIFIED","source":{"file":"<path or null>","line":null},"challenge":"<extractor finding>","override_reasoning":null,"risk_level":null}
```

**Choice B — OVERRIDE:** Ask "Reasoning?" then "Risk: HIGH/MEDIUM/LOW?"
```json
{"claim":"<text>","status":"VERIFIED_WITH_OVERRIDE","source":{"file":"<path or null>","line":null},"challenge":"<finding>","override_reasoning":"<engineer text>","risk_level":"<level>"}
```

**Choice C — BLOCK:**
```json
{"claim":"<text>","status":"NOT_FOUND","source":null,"challenge":"<finding>","override_reasoning":null,"risk_level":null}
```

Add to blocked list.

**Cache-write rule for challenge-loop outcomes:** Write all three outcomes (CONFIRM /
OVERRIDE / BLOCK) to the per-task `$CITATION` file with `cache_key` set, so a resume
of this same task honors prior engineer judgment. **Do not** write OVERRIDE or
CONFIRM-after-conflict records to the shared `$SHARED_CACHE` — engineer overrides
belong to a single task and should not auto-apply to other tickets. Only Step 6c's
`FOUND_MATCH` and `NET_NEW` outcomes (clean extractor results, no human judgment) are
eligible for the shared cache.

Finalize the claim report using the same recipe after completeness checks,
Step 6c's `[NEW]`/`[EXISTING]` mapping and this challenge loop. Use `schema` for
malformed/incomplete batches, `substantive` for unresolved findings requiring
repair, or `success` for accepted mapped outcomes (including `NET_NEW`). Finalize
before any repair reissue; budget accounting never replaces Step 8 approval.

---

## Step 8 — Gate evaluation

```bash
python3 - "$CITATION" << 'PYEOF'
import json, sys
path = sys.argv[1]
blocked = []
try:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            e = json.loads(line)
            if e.get("status") == "NOT_FOUND":
                blocked.append(e.get("claim", "(unknown)"))
except FileNotFoundError:
    print("GATE_ERROR: citation file not found"); sys.exit(1)
print(f"BLOCKED_COUNT: {len(blocked)}")
for c in blocked:
    print(f"  BLOCKED: {c}")
PYEOF
```

**If BLOCKED_COUNT > 0:**

```
ADVERSARIAL GATE: BLOCKED

Unresolved claims (status=NOT_FOUND, no override):
  [list]

To proceed: re-run /nightshift-adversarial <task-key> and for each blocked claim:
  - Choose B (OVERRIDE) with reasoning if the spec is still correct
  - Or update the spec, then re-run
```

Stop. Do not gate downstream.

**If BLOCKED_COUNT = 0:**

```
ADVERSARIAL GATE: APPROVED — all N claims verified or overridden with reasoning.
```

Continue to Step 9.

---

## Step 9 — Hot-spot briefing

Read `$CITATION`. Find all `VERIFIED_WITH_OVERRIDE` entries. Group by `risk_level`.

```
══════════════════════════════════════════════════════════════════
<task-key> Implementation Hot Spots

These spec claims were challenged during adversarial review.
Pay attention to these areas during /implement.
══════════════════════════════════════════════════════════════════

### HIGH RISK
- "<claim>" (<file>:<line or ?>)
  Extractor found: <challenge>
  Override: "<reasoning>"

### MEDIUM RISK
[same format, or "(none)"]

### LOW RISK
[same format, or "(none)"]

Full citation file: `.nightshift/<task-key>-citations.jsonl` (or the legacy task home)
══════════════════════════════════════════════════════════════════
```

If no overrides: `"All N claims verified — no hot spots."`

---

## Step 9.5 — Generate review digest + trim citations (token savings)

Now that the spec is APPROVED and the citation file is final, produce the two read-only
derivatives the downstream stages consume so they pay for the contract, not the rationale:

```bash
bash ~/.nightshift/scripts/nightshift-spec-digest.sh "$TASK"
bash ~/.nightshift/scripts/nightshift-citations-trim.sh "$TASK"
```

- `nightshift-spec-digest.sh` writes `docs/<task-key>/SPEC-DIGEST.md` — only the Acceptance Criteria
  and Guardrails sections. `/nightshift-review` reads this instead of the full `SPEC.md`, so the
  review lenses are neither billed for nor anchored by the Solution/TRD rationale.
- `nightshift-citations-trim.sh` writes the resolved state home's `<task-key>-citations-trim.jsonl` —
  claim + location + risk only, which `/nightshift-implement` reads during planning.

Both are non-fatal: a `SKIPPED`/`WARNING` line means the source was absent — warn and continue.
The digest is regenerated after the spec-lock in `/nightshift-implement` Step 0.5; generating it here
means review still has a digest even if implementation is run separately.

---

## Step 10 — Update tracker and bead

```bash
TRACKER="${TASK_DIR}/${TASK}.md"
if [ -f "$TRACKER" ]; then
  # Mark adversarial stage complete in the tracker
  sed -i '' 's|^- \[ \] /nightshift-adversarial.*|- [x] /nightshift-adversarial — claim verification (APPROVED)|' "$TRACKER"
fi
BD_ID=$([ -f "${PROJECT}/docs/${TASK}/.bd-id" ] && cat "${PROJECT}/docs/${TASK}/.bd-id" || echo "")
if [ -n "$BD_ID" ]; then
  bd note "$BD_ID" "Adversarial verification APPROVED. Citations: ${TASK_DIR#$PROJECT/}/${TASK}-citations.jsonl" 2>/dev/null || true
fi
```

---

## Step 11 — Handoff

Print:
> "Adversarial APPROVED. Hot-spot briefing above. **Next:** `/implement <task-key>` to build,
> or `/nightshift-eng <task-key>` to continue the orchestrated pipeline."
