---
name: nightshift-drift
description: "Spec ↔ implementation drift check. Reads SPEC.md, extracts the Files to Change table + acceptance criteria + claims, cross-references against the actual git diff. Surfaces: items in spec but missing from diff, files in diff but missing from spec, ACs not visibly addressed. Output saved to docs/<task-key>/DRIFT.md. Run /nightshift-drift <task-key>."
argument-hint: "<task-key>"
---

# /nightshift-drift — Spec vs Implementation Drift Check

Catches the gap between what the spec promised and what `/implement` actually did. Three
classes of drift get surfaced:

1. **Missing implementation** — file/AC was in the spec, not in the diff.
2. **Unspecified change** — file in the diff was not declared in spec.
3. **AC not addressed** — acceptance criterion has no visible coverage in the diff or in test files.

Output goes to `docs/<task-key>/DRIFT.md` and gates downstream.

**No gstack.** Don't invoke `/review`, `/qa`, `/health`. The diff parsing is plain `git diff`.

---

## Step 1 — Parse argument and resolve paths

```bash
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK="$ARGUMENTS"
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
DRIFT="${PROJECT}/docs/${TASK}/DRIFT.md"

mkdir -p "$TASK_DIR" "${PROJECT}/docs/${TASK}"
```

If `$ARGUMENTS` empty: print `"Usage: /nightshift-drift <task-key>"` and stop.
If `$SPEC` missing: print `"No spec at $SPEC. Run /nightshift-product first."` and stop.

---

## Step 2 — Get the diff

```bash
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
CHANGED=$(git diff --name-only "${BASE}...HEAD" 2>/dev/null)
if [ -z "$CHANGED" ]; then
  echo "NO_DIFF: no files changed vs ${BASE}. Drift check requires an implementation to compare against."
  exit 0
fi
echo "Comparing against base: $BASE"
echo "$CHANGED"
```

---

## Step 3 — Extract spec items

Read the full spec. Extract three lists:

### 3a. Files to Change
Parse the spec's "Files to Change" or equivalent table (look for `## Files to Change` heading,
fall back to any markdown table containing `path` or `file` columns). Build:

```
SPEC_FILES = [path1, path2, ...]
```

Tag each as `[CREATE]`, `[MODIFY]`, or `[DELETE]` if the table specifies; default `[MODIFY]`.

### 3b. Acceptance Criteria
Parse `## Acceptance Criteria` (or `## ACs`, `## Success Criteria`). Each bullet/numbered item
becomes one AC. Build:

```
ACS = [(id, text), ...]
```

### 3c. Behavioral claims
Re-use the citations from the resolved state home's `<task-key>-citations.jsonl` if it exists. Pull
all `VERIFIED` and `NET_NEW` entries — these are the specific behaviors the spec promised.

---

## Step 4 — Cross-reference

### 4a. Missing implementation (spec → diff)
For each `SPEC_FILES` entry:
- `[MODIFY]` or `[CREATE]` → must appear in `$CHANGED`
- `[DELETE]` → must NOT appear in `$CHANGED` (and the file must not exist anymore)

Items failing the check go into `MISSING_IMPL`.

### 4b. Unspecified change (diff → spec)
For each path in `$CHANGED`:
- If not in `SPEC_FILES`, add to `UNSPEC_CHANGE`

Apply allowlist (suppress these from drift report — they're routine):
- `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`
- `CHANGELOG.md`, `VERSION`
- resolved state home `<task-key>.md` (the tracker itself)
- `docs/<task-key>/*` (drift report and review will be written here)

Anything else in `UNSPEC_CHANGE` is reported.

### 4c. AC not addressed
For each AC:
- Search the diff (`git diff ${BASE}...HEAD`) for keywords from the AC text
- Search test files for the AC id or keyword
- If neither hits, add to `AC_UNCOVERED`

Use 2+ distinct keywords from the AC; if both hit somewhere in the diff, mark covered.
This is heuristic — false positives are surfaced as WARN, not BLOCK.

---

## Step 5 — Write DRIFT.md

```markdown
## Spec ↔ Implementation Drift

**Task:** <task-key>
**Date:** YYYY-MM-DD
**Base:** <BASE>
**Changed files:** N

---

### Missing Implementation
Spec listed these files; diff doesn't touch them.

| Severity | File | Spec marker | Notes |
|----------|------|-------------|-------|
[BLOCK rows for [CREATE] missing, WARN for [MODIFY] missing, BLOCK for [DELETE] still present]

### Unspecified Changes
Diff touches these files; spec didn't list them.

| Severity | File | Lines changed | Notes |
|----------|------|---------------|-------|
[WARN rows — could be legitimate, but engineer should confirm]

### Acceptance Criteria Coverage
| AC | Status | Evidence |
|----|--------|----------|
[COVERED / UNCOVERED / WARN per AC]

---

### Summary
- BLOCK: N
- WARN:  N

### Verdict
[APPROVE / REQUEST CHANGES]
[If REQUEST CHANGES: list BLOCKs]
```

---

## Step 6 — Gate verdict

```
BLOCK count: N
```

If N > 0:
```
NIGHTSHIFT-DRIFT GATE: REQUEST CHANGES — N drift items.
[list]
```
Stop.

If N = 0:
```
NIGHTSHIFT-DRIFT GATE: APPROVE
```
Continue.

---

## Step 7 — Update tracker and bead

```bash
TRACKER="${TASK_DIR}/${TASK}.md"
if [ -f "$TRACKER" ]; then
  sed -i '' 's|^- \[ \] /nightshift-drift.*|- [x] /nightshift-drift — drift check (APPROVE)|' "$TRACKER"
fi
BD_ID=$([ -f "${PROJECT}/docs/${TASK}/.bd-id" ] && cat "${PROJECT}/docs/${TASK}/.bd-id" || echo "")
if [ -n "$BD_ID" ]; then
  bd note "$BD_ID" "Drift check APPROVE. BLOCK: 0. WARN: <n>. Artifact: docs/${TASK}/DRIFT.md" 2>/dev/null || true
fi
```

Print:
> "Drift report: docs/<task-key>/DRIFT.md. **Next:** `/nightshift-preflight <task-key>` for the pre-deploy checklist."
