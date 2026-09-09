---
name: nightshift-qa
description: "Behavioral QA gate — runs the project's full Playwright suite locally as a regression check after code review and drift. Final behavioral proof plus PASS/SKIPPED browser results gate downstream; FAIL requests changes. Writes docs/<task-key>/QA.md. Run /nightshift-qa <task-key> after /nightshift-review and /nightshift-drift."
argument-hint: "<task-key> — matches docs/<task-key>/SPEC.md"
---

# /nightshift-qa — Behavioral QA Gate

Final QA combines the project's browser regressions with required task behavioral
proof after review and drift. `nightshift-pw.sh` can skip an absent Playwright
suite; that skip never waives deterministic final evidence or held-out prototype
evaluation. Development RED or prompt pass alone cannot satisfy final approval.

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

## Step 2.5 — Complete final behavioral proof

Follow `docs/BEHAVIOR-PROOF.md` in source (installed at
`${NIGHTSHIFT_HOME:-$HOME/.nightshift}/docs/nightshift-behavior-proof.md`). Require
the adopted public scenario artifact and existing development admission.

For required deterministic cases, retain actual passing ordinary test evidence
for the final source hashes. If review/drift/QA repairs changed bound files,
rerun the affected ordinary checks and refresh `docs/$TASK/proof-final.json`
through the trusted observer, then call the proof helper's `record-final
--project "$PROJECT" --task "$TASK" --evidence "docs/$TASK/proof-final.json"`.
Do not manufacture a passing observation from a reviewer label or old RED result.

For required prototype cases, invoke the proof helper's `run --project "$PROJECT"
--task "$TASK" --gate final`. It uses the independently retained private cases;
never copy their bodies, expected assertions, output or locator into GREEN context.
Failure/unknown blocks. Do not automatically repair from hidden output. Record
known exposure with `expose --case ID`; replacement requires independent review
and a new commitment/seal with retained budgets. No unchanged resampling or
budget reset can turn failure into fresh validation.

Every task, including not-applicable-only cases and no-Playwright projects, must
satisfy the final read-only gate:

```bash
python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-behavior-proof.py" \
  gate --project "$PROJECT" --task "$TASK" --gate final || exit $?
```

Require its pass outcome before recording QA approval. Missing helper, unknown,
stale source hashes, required case gaps or exhausted budgets stop this stage.
Retain only sanitized proof status and evidence digests in the public QA report.

---

## Step 3 — Write QA.md

```markdown
## Behavioral QA (nightshift-qa)
**Task:** <task-key> · **Date:** YYYY-MM-DD · **Runner:** nightshift-pw.sh (Playwright)
**Browser verdict:** PASS | FAIL | SKIPPED (no Playwright)
**Final behavioral proof:** pass | fail | unknown
**Overall verdict:** APPROVE only with final proof pass and browser pass/skip

### Summary
[one line: N passed / M failed, or "Playwright not present — skipped"]

### Evidence
[on FAIL: the failing spec names + the output tail from nightshift-pw.sh; full log: docs/<task-key>/QA-output.log]
```

---

## Step 4 — Gate

| Verdict | Gate |
|---|---|
| `PW_PASS` with final proof pass | `NIGHTSHIFT-QA GATE: APPROVE` — continue. |
| `PW_SKIPPED` with final proof pass | `NIGHTSHIFT-QA GATE: APPROVE (browser suite absent; final proof passed)` — continue. |
| Final proof fail/unknown/missing | `NIGHTSHIFT-QA GATE: REQUEST CHANGES` — stop; browser skip is insufficient. |
| `PW_FAIL` | `NIGHTSHIFT-QA GATE: REQUEST CHANGES` — surface the failing specs and stop. Do not gate downstream. |

On `REQUEST CHANGES`, repair the smallest authorized regression using only public
feedback. Intentional requirement or locked-test changes require independent
re-review and new seals, retaining earlier evidence and budgets. Do not rewrite
tests to bless a failure or expose held-out material to guide an automatic repair.
Then rerun the required ordinary checks and `/nightshift-qa <task-key>`.

---

## Step 5 — Update tracker and bead

Reach this step only after final proof pass and an accepted browser result.

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
