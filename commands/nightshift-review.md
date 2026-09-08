---
name: nightshift-review
description: "Post-implementation code review across six lenses: DRY, SOLID, ACID, CoC, Big O, and LLM trust boundaries. Each finding is HIGH/MEDIUM/LOW confidence — only HIGH+MEDIUM count toward BLOCK gate. Appends to a JSONL trend log so successive runs show deltas. Run /nightshift-review <task-key>."
argument-hint: "<task-key>"
---

# /nightshift-review — Post-Implementation Code Review

Reviews the files actually changed by `/implement` against six lenses. Each finding carries
a confidence level (HIGH/MEDIUM/LOW). Only HIGH+MEDIUM contribute to the BLOCK gate;
LOW findings are recorded as NOTEs only.

Trend log lives at the resolved state home's `review-history.jsonl` — every run appends a row,
and the next run shows deltas vs the previous (per lens, per severity).

**No gstack.** Do not invoke `/review` (gstack), `/health`, or `/autoplan`. The lens checks
below are run by the active runtime using file reads and repository searches over the changed files.

---

## Step 1 — Parse argument and resolve scope

```bash
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --shell) || exit $?
eval "$PROJECT_CONTEXT"
PROJECT="$NIGHTSHIFT_PROJECT_DIR"
TASK="$ARGUMENTS"
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
DIGEST="${PROJECT}/docs/${TASK}/SPEC-DIGEST.md"
REVIEW="${PROJECT}/docs/${TASK}/REVIEW.md"
HISTORY="${TASK_DIR}/review-history.jsonl"

mkdir -p "$TASK_DIR" "${PROJECT}/docs/${TASK}"

# Context budget check — bail to a resume hint if the wall is near.
CTX_RC=0; bash ~/.nightshift/scripts/nightshift-context-check.sh "review" "$TASK" || CTX_RC=$?
if [ "$CTX_RC" -eq 2 ]; then exit 1; fi

# The lens pass reads the digest (ACs + guardrails only) when present, so it judges the
# diff against the contract — not the author's Solution/TRD rationale. Fall back to the
# full spec only if the digest is absent (pipeline run before the digest stage).
SPEC_FOR_REVIEW="$SPEC"
[ -f "$DIGEST" ] && SPEC_FOR_REVIEW="$DIGEST"
echo "Spec source for lenses: ${SPEC_FOR_REVIEW#$PROJECT/}"
```

If `$ARGUMENTS` empty: print `"Usage: /nightshift-review <task-key>"` and stop.

If `$SPEC` missing: print `"No spec at $SPEC — run /nightshift-product first."` and stop.

> Steps 3–5 read **`$SPEC_FOR_REVIEW`** (the digest when present) for the acceptance criteria
> and guardrails the lenses check against — never the full `SPEC.md` when a digest exists.

---

## Step 2 — Determine files to review

Two sources, in priority order:

1. **Files actually changed by `/implement`** — `git diff --name-only <base>...HEAD` where
   base is `main` (or whatever `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` returns). This is the truth.
2. **Files declared in spec's "Files to Change" table** — fallback if no diff (pre-implement
   baseline review).

```bash
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
CHANGED=$(git diff --name-only "${BASE}...HEAD" 2>/dev/null)
if [ -n "$CHANGED" ]; then
  REVIEW_MODE="post-impl"
  echo "Reviewing files changed vs $BASE"
else
  REVIEW_MODE="baseline"
  echo "No diff — reviewing files declared in spec"
fi
```

Read each file fully. Skip files that no longer exist.

---

## Step 2b — Diff-hash cache lookup (skip lenses on a clean re-run)

If the diff hasn't changed since the prior review run **and** REVIEW.md hasn't been
edited by hand, skip Steps 3-5 and replay the existing REVIEW.md verdict. This handles
the common "re-ran /nightshift-eng without committing" case at near-zero cost.

```bash
REVIEW_CACHE="${TASK_DIR}/${TASK}-review-cache.jsonl"
CACHE_HIT=false
DIFF_SHA=""

if [ "$REVIEW_MODE" = "post-impl" ]; then
  DIFF_SHA=$(git diff "${BASE}...HEAD" \
    | { command -v sha256sum >/dev/null 2>&1 && sha256sum || shasum -a 256; } \
    | cut -d' ' -f1)

  if [ -f "$REVIEW_CACHE" ] && [ -f "$REVIEW" ]; then
    HIT=$(grep -F "\"diff_sha\":\"${DIFF_SHA}\"" "$REVIEW_CACHE" | tail -1 || true)
    if [ -n "$HIT" ]; then
      PRIOR_MD5=$(printf '%s' "$HIT" | jq -r '.review_md5')
      CURRENT_MD5=$(md5 -q "$REVIEW" 2>/dev/null \
        || md5sum "$REVIEW" 2>/dev/null | cut -d' ' -f1)
      if [ "$PRIOR_MD5" = "$CURRENT_MD5" ]; then
        CACHE_HIT=true
        echo "REVIEW_CACHE_HIT: diff unchanged since prior run; replaying REVIEW.md."
      fi
    fi
  fi
fi
```

If `$CACHE_HIT` is true: skip Steps 3-5, jump directly to Step 6 (append a trend-log
entry with `cache_hit: true`) and then Step 7 (gate verdict — parse the existing
REVIEW.md's `### Summary` block for BLOCK/WARN/NOTE counts).

If `$CACHE_HIT` is false: continue to Step 2c as usual.

---

## Step 2c — TDD integrity check (gate)

Before judging the diff on quality, verify the TDD contract held: no non-`nightshift-bot` commit
touched a locked path (the sealed spec, or the sealed RED-phase tests) after the lock point.

```bash
INTEGRITY=$(bash ~/.nightshift/scripts/nightshift-tdd-integrity-check.sh "$TASK")
echo "$INTEGRITY"
```

| Output | Action |
|---|---|
| `TDD_INTEGRITY: PASS` | Continue to Step 3. |
| `TDD_INTEGRITY: SKIPPED` | No locks recorded (implementation skipped the TDD locks). Print one line and continue. |
| `TDD_INTEGRITY: FAIL` | A locked path was tampered with after sealing. **Surface every violation and stop** — this gates downstream exactly like a BLOCK finding. Do not run the lenses; the diff cannot be trusted until the tampering is reverted or the spec is re-sealed intentionally. |

On `FAIL`, emit:

```
NIGHTSHIFT-REVIEW GATE: REQUEST CHANGES — TDD integrity violated.
[violations from the script]
```

and stop. Do not gate downstream.

---

## Step 3 — Run six lenses

Every finding must include: `lens`, `severity` (BLOCK/WARN/NOTE), `confidence`
(HIGH/MEDIUM/LOW), `file:line`, and a one-sentence description. **No location → not a finding.**

### DRY
Duplicated logic, copy-pasted blocks, parallel data structures, inline constants repeated > 1×,
type predicates written multiple times for the same shape.

### SOLID
- **S** — function/component doing more than one thing
- **O** — switch-on-type or if/else chains that will grow with new cases
- **L** — implementations breaking the interface contract
- **I** — fat interfaces where most callers use 2–3 fields
- **D** — concrete dependencies wired into business logic

### ACID (state-mutating code only — context, store, API, DB writes)
- **A** — multiple `setState`/writes that should batch
- **C** — missing validation before writes, invalid intermediate states
- **I** — race conditions in async code, missing effect cleanup
- **D** — user input or critical data lost without recovery

### CoC — Convention over Configuration
Names, file placement and patterns against resolved project conventions
(`docs/PROJECT-CONTEXT.md` in the Nightshift source (installed at
`${NIGHTSHIFT_HOME:-$HOME/.nightshift}/docs/nightshift-project-context.md`)) and adjacent code.

### Big O
- **BLOCK**: O(n²)+ in hot path, N+1 query, unbounded DB fetches
- **WARN**: wrong data structure for access pattern, redundant passes over non-trivial collections
- **NOTE**: minor inefficiency at current scale

### LLM Trust Boundary
Any user input, LLM output, or external response flowing into:
- `eval`, `exec`, dynamic `import`, `Function()` constructor → **BLOCK**
- Shell exec (`spawn`, `exec`, backticks, template strings into bash) without sanitizer → **BLOCK**
- SQL string concatenation (no parameterized query) → **BLOCK**
- File path concatenation without `path.resolve` + boundary check → **WARN**
- `dangerouslySetInnerHTML` / `v-html` / direct `.innerHTML =` with untrusted source → **BLOCK**
- HTTP redirect / `Location` header from untrusted source → **WARN**
- Tool-use loop where LLM output is fed back as instruction without validation → **WARN**

### Confidence calibration
- **HIGH** — finding is mechanically verifiable; reproducible from the code as-is
- **MEDIUM** — likely a real issue but depends on runtime context not visible in the diff
- **LOW** — pattern smell; might be fine in this codebase

**Only HIGH and MEDIUM findings can be BLOCK.** A LOW BLOCK is contradictory — downgrade to WARN.

**Exceptions:** one-time setup code, test data construction, provably bounded datasets.

---

## Step 4 — Compute deltas vs last run

```bash
PREV=$(grep -E "\"task\":\s*\"${TASK}\"" "$HISTORY" 2>/dev/null | tail -1)
```

If `$PREV` exists, parse counts and compute deltas per lens × severity:
```
DRY:    BLOCK 0 (—)  WARN 2 (-1)  NOTE 4 (+1)
SOLID:  BLOCK 1 (+1) WARN 0 (—)   NOTE 2 (-3)
...
```

If no prior run, print `"First review for ${TASK} — no deltas to compare."`.

---

## Step 5 — Save REVIEW.md artifact

Write to `$REVIEW`:

```markdown
## Code Review (nightshift-review)

**Task:** ${TASK}
**Date:** YYYY-MM-DD
**Mode:** post-impl | baseline
**Scope:** N files (vs ${BASE})
**Reviewer:** nightshift-review harness

---

### DRY
| Severity | Confidence | Finding | Location |
|----------|-----------|---------|----------|
[rows or "No findings."]

### SOLID
| Severity | Confidence | Principle | Finding | Location |
|----------|-----------|-----------|---------|----------|

### ACID
| Severity | Confidence | Property | Finding | Location |
|----------|-----------|----------|---------|----------|

### CoC
| Severity | Confidence | Finding | Location |
|----------|-----------|---------|----------|

### Big O
| Severity | Confidence | Complexity | Finding | Location |
|----------|-----------|-----------|---------|----------|

### LLM Trust Boundary
| Severity | Confidence | Vector | Finding | Location |
|----------|-----------|--------|---------|----------|

---

### Summary
- BLOCK: N (HIGH: x, MEDIUM: y)
- WARN:  N
- NOTE:  N

### Trend (vs last run)
[per-lens deltas, or "first run" message]

### Verdict
[APPROVE / REQUEST CHANGES]
[If REQUEST CHANGES: list BLOCK items]
```

---

## Step 5b — Write to review cache (cache-miss path only)

After Step 5 wrote REVIEW.md, append a cache record so the next clean re-run can
short-circuit via Step 2b. Skip this if `$CACHE_HIT` was true (we already have a
record for this diff_sha).

```bash
if [ "$CACHE_HIT" != "true" ] && [ "$REVIEW_MODE" = "post-impl" ] && [ -n "$DIFF_SHA" ]; then
  REVIEW_MD5=$(md5 -q "$REVIEW" 2>/dev/null \
    || md5sum "$REVIEW" 2>/dev/null | cut -d' ' -f1)
  jq -n \
    --arg task "$TASK" \
    --arg sha "$DIFF_SHA" \
    --arg base "$BASE" \
    --arg head "$(git rev-parse HEAD)" \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg path "$REVIEW" \
    --arg md5 "$REVIEW_MD5" \
    '{task:$task, diff_sha:$sha, base:$base, head_sha:$head, timestamp:$ts, review_path:$path, review_md5:$md5}' \
    >> "$REVIEW_CACHE"
fi
```

---

## Step 6 — Append to trend log

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n \
  --arg task "$TASK" \
  --arg ts "$TS" \
  --arg mode "$REVIEW_MODE" \
  --argjson cache_hit "$([ "$CACHE_HIT" = "true" ] && echo true || echo false)" \
  --argjson counts '<lens-by-severity-counts-from-step-3>' \
  '{task: $task, timestamp: $ts, mode: $mode, cache_hit: $cache_hit, counts: $counts}' \
  >> "$HISTORY"
```

On a cache hit, `counts` is parsed from the existing REVIEW.md's `### Summary` block
rather than recomputed from a (skipped) Step 3.

---

## Step 7 — Gate verdict

```
BLOCK count (HIGH + MEDIUM only): N
```

If N > 0:
```
NIGHTSHIFT-REVIEW GATE: REQUEST CHANGES — N blocking findings.
[list them]
```
Stop. Do not gate downstream.

If N = 0:
```
NIGHTSHIFT-REVIEW GATE: APPROVE
```
Continue to Step 8.

---

## Step 8 — Update tracker and bead

```bash
TRACKER="${TASK_DIR}/${TASK}.md"
if [ -f "$TRACKER" ]; then
  sed -i '' 's|^- \[ \] /nightshift-review.*|- [x] /nightshift-review — code review (APPROVE)|' "$TRACKER"
fi
BD_ID=$([ -f "${PROJECT}/docs/${TASK}/.bd-id" ] && cat "${PROJECT}/docs/${TASK}/.bd-id" || echo "")
if [ -n "$BD_ID" ]; then
  bd note "$BD_ID" "Review APPROVE. BLOCK: 0. WARN: <n>. NOTE: <n>. Artifact: docs/${TASK}/REVIEW.md" 2>/dev/null || true
fi
```

Print:
> "Review complete: docs/<task-key>/REVIEW.md. **Next:** `/nightshift-drift <task-key>` to check spec ↔ diff alignment."
