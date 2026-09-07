---
name: nightshift-preflight
description: "Pre-deploy gate for the nightshift-* pipeline. Structured interview, script-safety validation, and a deployment manifest written to docs/<task-key>/PREFLIGHT.md. Produces the checklist only — executes nothing. Run /nightshift-preflight <task-key> after /nightshift-drift."
argument-hint: "<task-key> [env] — e.g. MVP-1, MVP-1 production"
---

# /nightshift-preflight — Pre-Deploy Gate

Conducts a structured interview and writes a deployment manifest. **Executes nothing** — no
push, no migration, no deploy. `/nightshift-deploy` is the only stage that acts, and it refuses to
start without the artifact this command produces (`commands/nightshift-deploy.md:33`).

Source-agnostic by construction: no ticket-system transitions, no comment posting, no
wiki/Confluence write-back. The upstream ticket stays the source of truth and is updated by a
human, or by `/nightshift-deploy` if the project wires that itself.

---

## Step 1 — Parse and resolve paths

```bash
TASK="${1:?Usage: /nightshift-preflight <task-key> [env]}"
ENV="${2:-}"
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DIR="${PROJECT}/docs/${TASK}"
SPEC="${DIR}/SPEC.md"
REVIEW="${DIR}/REVIEW.md"
DRIFT="${DIR}/DRIFT.md"
QA="${DIR}/QA.md"
PREFLIGHT="${DIR}/PREFLIGHT.md"
STATE_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
TRACKER="${STATE_DIR}/${TASK}.md"
BD_ID=$(cat "${DIR}/.bd-id" 2>/dev/null || true)
```

Hard preconditions:

- `$SPEC` exists → else `"No spec — run /nightshift-product $TASK first."` and stop.
- `$PREFLIGHT` already exists → show it and ask: *"Preflight exists. Regenerate? Y/N"*. Never
  silently overwrite an approved manifest.

Read `$SPEC` and, when present, `$REVIEW`, `$DRIFT`, and `$QA` for context. Their verdicts feed
the gates table in Step 4 — do not re-derive what those stages already decided.

---

## Step 2 — The interview

Ask these in sequence. One question at a time; do not batch them. Carry forward anything the
artifacts already answer and say so rather than asking again ("Spec says 3 files, no
migrations — confirming: correct?").

| # | Captures |
|---|---------|
| 1 | **What ships** — task key, branch, commit range, PR if one exists |
| 2 | **Target environment** — local / staging / production (use `$ENV` if passed; still confirm) |
| 3 | **What changed** — code, schema/migrations, config, dependencies |
| 4 | **Migration or data scripts** — paths in source control, and their paired rollback scripts |
| 5 | **Config changes** — env vars, feature flags, secrets, and where they must be set |
| 6 | **Who** — who executes, who verifies, who has rollback authority (all three may be the same person) |
| 7 | **Blast radius** — downstream consumers, cross-repo dependencies, anything that must ship in order |

---

## Step 3 — Script safety validation

Runs only when Q4 named any migration or data script. Each rule is checked against the actual
files, not against the answer text.

| Rule | Severity | Condition |
|------|----------|-----------|
| R1 | **BLOCK** | Every script named must be committed — `git ls-files --error-unmatch <path>` succeeds. No ad-hoc or uncommitted scripts. |
| R2 | **BLOCK** | Every destructive script (`DROP`, `DELETE`, `TRUNCATE`, `ALTER ... DROP`, destructive `UPDATE` without `WHERE`) has a paired rollback script, named in Q4. |
| R3 | **BLOCK** | Every migration is re-entrant — `IF NOT EXISTS`, `CREATE OR ALTER` / `CREATE OR REPLACE`, `WHERE NOT EXISTS` / `MERGE` / `ON CONFLICT` — unless explicitly marked `-- non-reentrant by design: <reason>`. Matches the same rule in `agents/nightshift-engineer.md`. |
| R4 | **WARN** | Scripts touching shared or cross-team data. Surface it; do not block. |

A **BLOCK** halts manifest generation. Report which rule, which file, and what fixes it. Do not
write a partial PREFLIGHT.md — a manifest that exists is a manifest `/nightshift-deploy` will trust.

---

## Step 4 — Write the manifest

Write `docs/<task-key>/PREFLIGHT.md`:

```markdown
# Preflight — <task-key>

**Generated:** <ISO-8601 UTC>
**Environment:** <env>
**Branch:** <branch>  **Base:** <base>  **Commit:** <short-sha>
**Bead:** <bd-id or "—">

## What ships
<one-paragraph summary + the commit range or PR link>

## Pre-deploy gates
| Gate | Source | Status |
|---|---|---|
| Spec exists and approved | `docs/<task-key>/SPEC.md` | ✅ / ❌ |
| Adversarial verification | citations log | ✅ APPROVED / ⚠️ OVERRIDE / ❌ |
| Code review | `REVIEW.md` | ✅ PASS / ⚠️ WARN / ❌ BLOCK |
| Drift check | `DRIFT.md` | ✅ / ⚠️ / ❌ |
| Behavioral QA | `QA.md` | ✅ PASS / ⏭ SKIPPED / ❌ FAIL |
| Tests green | last run | ✅ / ❌ |
| Script safety (R1–R4) | Step 3 | ✅ / ⚠️ WARN / ❌ BLOCK |

## Deployment steps
<ordered, copy-pasteable commands — the executor runs these, this command does not>

## Validation (post-deploy)
<what to check, in what order, and what "good" looks like>

## Rollback plan
<exact steps and the paired rollback scripts from Q4; who has authority>

## Roster
| Role | Who |
|---|---|
| Executor | |
| Verifier | |
| Rollback authority | |

## Risk flags
<every WARN from Step 3, plus anything Q7 surfaced>

## Verdict
**<READY / READY WITH RISKS / BLOCKED>** — <one-line justification>
```

A gate that is ❌ makes the verdict **BLOCKED**. A gate that is ⚠️ makes it **READY WITH
RISKS** and the risk must appear under Risk flags. Do not write **READY** over an ❌.

---

## Step 5 — Update tracker and bead

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
[ -f "$TRACKER" ] && sed -i '' "s|^[⬜⏳] /nightshift-preflight.*|✅ /nightshift-preflight — pre-deploy checklist (complete) [$TS]|" "$TRACKER"
if [ -n "$BD_ID" ] && bash ~/.nightshift/scripts/nightshift-capability.sh --has bd; then
  bd note "$BD_ID" "preflight: <verdict> — docs/${TASK}/PREFLIGHT.md"
fi
```

`bd` is optional. When it is absent the manifest is still authoritative — beads is the local
ledger, never the gate.

---

## Step 6 — Handoff

> "Preflight complete: `docs/<task-key>/PREFLIGHT.md` (**<verdict>**).
> **Next:** `/nightshift-deploy <task-key> [env]` to ship."

On **BLOCKED**, name the failing gate and stop. Do not suggest `/nightshift-deploy`.

---

## Rules

- **Produces a checklist; executes nothing.** No push, no migration, no deploy, no PR merge.
- **Never overwrite an approved manifest** without an explicit Y.
- **Never write READY over a failing gate.** The verdict is mechanical, not a judgment call.
- **No ticket-system side effects.** No status transitions, no comments. Source-agnostic.
- **BLOCK means stop**, not "note it and continue".
