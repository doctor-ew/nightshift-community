---
name: nightshift-qa
description: "Behavioral QA gate — runs the project's full Playwright suite locally as a regression check after code review and drift. PASS/SKIPPED (no Playwright) gates downstream; FAIL requests changes. Writes docs/<task-key>/QA.md. Run /nightshift-qa <task-key> after /nightshift-review and /nightshift-drift."
argument-hint: "<task-key> — matches docs/<task-key>/SPEC.md"
---

# /nightshift-qa — Behavioral QA Gate

The pipeline's first **behavioral** gate: code review (`nightshift-review`) proves the diff is
well-built and drift (`nightshift-drift`) proves it matches the spec — `nightshift-qa` proves it actually
**runs**. It executes the project's full Playwright suite locally as a regression check: did
this ticket break any existing end-to-end behavior?

**Zero-cost when Playwright is absent.** `nightshift-pw.sh` detects `@playwright/test` / a
`playwright.config.*`; with none present the gate returns `SKIPPED` and approves — projects
without E2E coverage are not penalized.

**No gstack.** Does not invoke `/qa`, `/browse`, or `/canary`. The runner is `nightshift-pw.sh`
(local), which delegates to the project's own Playwright + package manager.

---

## Step 1 — Parse and resolve

```bash
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --shell) || exit $?
eval "$PROJECT_CONTEXT"
PROJECT="$NIGHTSHIFT_PROJECT_DIR"
TASK="$ARGUMENTS"
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
QA="${PROJECT}/docs/${TASK}/QA.md"
mkdir -p "$TASK_DIR" "${PROJECT}/docs/${TASK}"

[ -z "$TASK" ] && { echo "Usage: /nightshift-qa <task-key>"; exit 1; }

CTX_RC=0; bash ~/.nightshift/scripts/nightshift-context-check.sh "qa" "$TASK" || CTX_RC=$?
if [ "$CTX_RC" -eq 2 ]; then exit 1; fi
```

If `$SPEC` missing: `"No spec at $SPEC — run /nightshift-product first."` and stop.

---

## Step 2 — Run the suite

```bash
OUTLOG="${PROJECT}/docs/${TASK}/QA-output.log"
RESULT=$(bash ~/.nightshift/scripts/nightshift-pw.sh "$TASK" --run --label qa --out "$OUTLOG")
echo "$RESULT"
VERDICT=$(echo "$RESULT" | grep -oE 'PW_(PASS|FAIL|SKIPPED)' | head -1)
```

`nightshift-pw.sh` picks the project's package manager by lockfile and prefers a `test:e2e` script
if the project declares one. It targets the local app (Playwright's own `webServer` config
starts it when configured) — `nightshift-qa` does **not** orchestrate app startup; that is the
project's `playwright.config` responsibility (CoC).

---

## Step 3 — Write QA.md

```markdown
## Behavioral QA (nightshift-qa)
**Task:** <task-key> · **Date:** YYYY-MM-DD · **Runner:** nightshift-pw.sh (Playwright)
**Verdict:** PASS | FAIL | SKIPPED (no Playwright)

### Summary
[one line: N passed / M failed, or "Playwright not present — skipped"]

### Evidence
[on FAIL: the failing spec names + the output tail from nightshift-pw.sh; full log: docs/<task-key>/QA-output.log]
```

---

## Step 4 — Gate

| Verdict | Gate |
|---|---|
| `PW_PASS` | `NIGHTSHIFT-QA GATE: APPROVE` — continue. |
| `PW_SKIPPED` | `NIGHTSHIFT-QA GATE: APPROVE (no Playwright — skipped)` — continue. |
| `PW_FAIL` | `NIGHTSHIFT-QA GATE: REQUEST CHANGES` — surface the failing specs and stop. Do not gate downstream. |

On `REQUEST CHANGES`, the engineer fixes the regression (or the spec/tests if the behavior
intentionally changed — re-sealing tests via the TDD lock if a locked spec must change) and
re-runs `/nightshift-qa <task-key>`.

---

## Step 5 — Update tracker and bead

```bash
TRACKER="${TASK_DIR}/${TASK}.md"
if [ -f "$TRACKER" ] && [ "$VERDICT" != "PW_FAIL" ]; then
  sed -i '' "s|^⏳ /nightshift-qa.*|✅ /nightshift-qa — behavioral QA (${VERDICT})|" "$TRACKER" 2>/dev/null || true
fi
BD_ID=$([ -f "${PROJECT}/docs/${TASK}/.bd-id" ] && cat "${PROJECT}/docs/${TASK}/.bd-id" || echo "")
[ -n "$BD_ID" ] && bd note "$BD_ID" "QA ${VERDICT}. Artifact: docs/${TASK}/QA.md" 2>/dev/null || true
```

Print:
> "QA complete: docs/<task-key>/QA.md (`<verdict>`). **Next:** `/nightshift-preflight <task-key>`."
