---
name: nightshift-implement
description: "TDD-aware implementation stage for the nightshift-* pipeline. Seals the spec (spec-lock), runs the RED phase under an agent firewall, locks the failing tests under the nightshift-bot identity (red-lock), detects already-fixed-upstream, then writes the GREEN fix. Supervised by default; autonomous under AUTONOMOUS=true. Never commits the final diff or opens a PR. Run /nightshift-implement <task-key>."
argument-hint: "<task-key> — matches docs/<task-key>/SPEC.md"
---

# /nightshift-implement — TDD-Aware Implementation

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

The nightshift's build stage. Same spine as `/implement` (branch → approaches → plan →
build → test → hand off) with four mechanics layered on so "tests went green" is provable,
not assertable:

1. **Spec-lock** — seal `SPEC.md` under `nightshift-bot@local` before any code is written.
2. **Agent firewall** — the implementation agent never sees the test source, so the RED
   phase stays epistemically independent (it designs to the spec, not to the assertions).
3. **RED-lock** — after the failing tests are written and confirmed RED, seal them under
   `nightshift-bot@local`. `/nightshift-review` later fails if a non-bot commit touched a locked path.
4. **Already-fixed-upstream** — if the new tests pass on unpatched code, there is nothing
   to build; exit cleanly without consuming retry budget.

**No gstack.** Never invoke `/ship`, `/qa`, `/review` (gstack), `/health`, or `/autoplan`.
**Never commit the final diff. Never push. Never open a PR.** That is `/nightshift-deploy`'s job.

---

## Modes

- **Supervised** (default — `AUTONOMOUS` unset/false): interactive gates at approach,
  and plan. Agents return prose.
- **Autonomous** (`AUTONOMOUS=true`, set by `/nightshift-batch`): no interactive gates — pick the
  conservative approach, proceed on the plan, and return the Step 9 JSON contract. Retry
  budget applies.

```bash
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "$ARGUMENTS") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
TASK=$(jq -r '.arguments' <<< "$STAGE_ARGS")
[ -z "$TASK" ] && { echo "Usage: /nightshift-implement <task-key> [--base REF]"; exit 1; }
```

Before any context/state helper or spec-lock writes, parse optional `--base REF` as literal
arguments and remove it from `TASK`. Use `nightshift-worktree.sh prepare "$TASK" --project
"$PROJECT"` with that exact `--base` value, then change directory and `CLAUDE_PROJECT_DIR`
to the returned `.worktree`. A failed prepare stops only this ticket in factory mode.

If eng/batch already prepared this exact context, do not call clean-only prepare after
product has written this ticket's files. Validate the common-Git-dir receipt at
`<common-git-dir>/nightshift/worktrees/TASK.json`: required version/field types, task,
repository, canonical worktree equal to the current checkout, `nightshift/TASK` branch,
registered worktree, prepared status, full base SHA ancestral to HEAD, and any explicit base
resolving to that same SHA. A matching `NIGHTSHIFT_PREPARED_TASK` alone is insufficient.
Allow existing in-progress product/state changes only after this ownership validation;
reject mismatches and other-task lease/scope owners. Do not adopt an unreceipted checkout.

For standalone entry with a spec only in the caller, prepare first, then copy only the
requested `docs/TASK/` artifacts into the returned checkout (preserve caller bytes). If the
spec already exists in the worktree, use it and reject conflicting copies rather than
silently overwriting it.

```bash
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
bash ~/.nightshift/scripts/nightshift-scope-activate.sh "$TASK" \
  --project "$PROJECT" --spec "$SPEC" || exit 1
```

Only the guarded activation helper publishes scope. Keep the lease throughout eng's later
stages; standalone completion calls `nightshift-worktree.sh finish "$TASK" --project
"$PROJECT"` after the handoff artifacts are written. Finish retains dirty worktree files
and branches and moves only matching ownership into retained retirement metadata.

If `$SPEC` missing — hard stop: `"No spec at docs/${TASK}/SPEC.md. Run /nightshift-product first. No build without a spec."`

---

## Step -1 — Context budget check

```bash
CTX_RC=0; bash ~/.nightshift/scripts/nightshift-context-check.sh "implement" "$TASK" || CTX_RC=$?
if [ "$CTX_RC" -eq 2 ]; then exit 1; fi
```

---

## Step 0 — Load spec

Read `$SPEC` fully. Extract:
- Acceptance-criteria count (numbered items under `## Acceptance Criteria`)
- Files-to-change count (rows in the `## Files to Change` table)
- Ticket type (`Bug` vs `Feature`)

---

## Step 0.5 — Spec-lock + token-savings artifacts

Seal the approved spec under the bot identity, then regenerate the review digest and the
trimmed citations from the sealed spec.

```bash
bash ~/.nightshift/scripts/nightshift-tdd-spec-lock.sh "$TASK"
bash ~/.nightshift/scripts/nightshift-spec-digest.sh "$TASK"
bash ~/.nightshift/scripts/nightshift-citations-trim.sh "$TASK"
```

- `SPEC_LOCK_SKIPPED: SPEC.md not found` → warn and continue (should not happen — Step 0 guarded).
- `SPEC_LOCK_SHA:` → noted; also written to the resolved state home's `${TASK}.locks` automatically.
- Digest/citation skips are non-fatal — warn and continue.

The implementation agent reads the resolved state home's `${TASK}-citations-trim.jsonl` for claim
detail (claim + location + risk only — not the full challenge/override prose).

---

## Step 1 — Confirm isolated context

Isolation was established at entry, before spec-lock or state writes. Use the recorded
`nightshift/TASK` branch; no inline branch, stash, or dirty-checkout menu is needed.

---

## Step 2 — Solution approaches

Read the spec's `## Solution` and the relevant code. Present **2–3 genuinely distinct**
approaches (always one conservative/minimal-change and one that follows the spec most directly):

```
### Approach A — [Name]
[2–3 sentences] · Pros · Cons · Effort: Quick(<1h)|Short(1–4h)|Medium(1–2d)|Large(3d+)
```

**Supervised:** ask which approach; wait. **Autonomous:** select the conservative approach,
state which and why in one line, proceed.

---

## Step 3 — Implementation plan

```
## Implementation Plan
### Blast Radius — Files / Modules / Cross-team (flag shared contracts loudly)
### Sequence — numbered, tests FIRST (RED before GREEN)
### Risks
### Effort estimate
```

The sequence **must** write the failing tests before any production code — RED precedes GREEN.

**Supervised:** "Does this plan look right?" — wait for explicit approval. **Autonomous:** record
the plan to the progress file and proceed.

---

## Step 4 — Progress file

Write the resolved state home's `<task-key>.md` if `/nightshift-eng` hasn't already (it owns the
Pipeline Stages section; only add an `## Implementation` block — never clobber its table):

```markdown
## Implementation
**Branch:** <branch> · **Approach:** <name> · **Started:** <YYYY-MM-DD>
- [ ] RED: write failing tests
- [ ] red-lock
- [ ] GREEN: implementation
- [ ] tests green
- [ ] hand off to /nightshift-review
```

---

## Step 5 — RED phase (agent firewall applies)

Write the failing tests named in the spec's Files-to-Change table. Confirm each fails with a
**relevant assertion error** (not a syntax/import error — a wrong test isn't a RED test).

**Agent firewall — applies when delegating the GREEN implementation in Step 7:**

| Agent | Allowed context | Prohibited context |
|---|---|---|
| **nightshift-engineer** | SPEC-DIGEST.md (ACs + guardrails), source under change, trimmed citations | Test source files; any tester output |
| **nightshift-architect** | same as nightshift-engineer | same as nightshift-engineer |
| **nightshift-run-all-tests** | no restriction (runs commands; no design role) | — |

Model, provider, and effort are **not** listed here — they resolve per dispatch from
`routing.json` on `(role, gear)`. See README "Agent routing".

Rationale: if the implementation agent already knows what the tests assert, it can satisfy the
assertions without designing to the spec. The firewall preserves that independence. **You** (the
orchestrator) write the tests in this step; the delegated agent in Step 7 does not receive them.

---

## Step 5.5 — Already-fixed-upstream detection (after RED, before any fix)

Run the new tests against the **unpatched** code:

- RED produced the expected failing assertion(s) → the defect is present. Continue to Step 6.
- **All** new tests pass on unpatched code → already fixed upstream. Terminal, **non-failure**
  exit; does **not** consume retry budget.

Already-fixed-upstream exit:
1. Note it in the progress file and (if a bead exists) `bd note "$BD_ID" "already-fixed-upstream: tests pass on unpatched code"`.
2. **Supervised:** report and stop — ask the engineer to confirm before closing.
   **Autonomous:** return the Step 9 contract with `status:"SKIP"`, `reason:"already-fixed-upstream"`.

---

## Step 6 — RED-lock

With the failing tests written and confirmed RED, seal them **before** writing fix code:

```bash
bash ~/.nightshift/scripts/nightshift-tdd-red-lock.sh "$TASK"
```

- `RED_LOCK_SHA:` → tests sealed under `nightshift-bot@local`; SHA recorded in `.locks`.
- `RED_LOCK_SKIPPED: no test files to stage` → tests weren't left uncommitted. Ensure the new
  tests are written and **not yet committed**, then re-run. (red-lock is the thing that commits
  them — do not pre-commit tests yourself.)

---

## Step 7 — GREEN phase

Route by the same thresholds as `/implement`:

| Condition | Agent |
|---|---|
| AC count ≥ 10 OR files ≥ 5 OR spans multiple modules | nightshift-architect |
| else | nightshift-engineer |

Set `ROLE` to the selected table entry. Write only the firewall-approved spec
digest, trimmed citations and source context to `docs/$TASK/implementation.in.md`;
never include tests, RED output or hidden assertions. Invoke the shared dispatcher:

```bash
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-agent.sh" \
  "$ROLE" --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --in "docs/$TASK/implementation.in.md" \
  --out "docs/$TASK/implementation.out.json"; then
  jq '{status,reason,results,artifacts}' "docs/$TASK/implementation.out.json"
else
  jq '{status,reason}' "docs/$TASK/implementation.out.json"
  # Preserve the existing scoped repair/escalation policy.
fi
```

Require SUCCESS and verify `.results.files_changed` against actual files and the
spec. Persist `.artifacts.provider` from the normalized SUCCESS receipt to
`docs/$TASK/implementation-author-provider.txt` for later verification; never
guess it from ROLE. FAIL/transport failures enter the existing retry budget;
SKIP cannot satisfy GREEN. Codex/local are explicitly read-only, so filesystem
implementation requires a separately authorized integration. Missing edits fail
the implementation gate; do not silently expand sandbox authority.

Apply the Step 5 firewall to the delegation prompt. Both agents:
- follow the spec's ACs as the checklist — nothing more, nothing less
- follow the repo's CLAUDE.md conventions
- **stop and flag** any file not in the Files-to-Change table before touching it
- **stop and flag** an incomplete/wrong spec — never improvise

If an agent returns `## AGENT BLOCKED`, surface it verbatim (supervised) or fold it into the
Step 9 contract as `FAIL` (autonomous).

---

## Step 8 — Tests green

Prepare `docs/$TASK/test-runner.in.md` with the project, appropriate suite commands
and report artifact path, and invoke **nightshift-run-all-tests** through the same
file protocol:

```bash
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-agent.sh" \
  nightshift-run-all-tests --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --in "docs/$TASK/test-runner.in.md" \
  --out "docs/$TASK/test-runner.out.json"; then
  jq '{status,reason,results,artifacts}' "docs/$TASK/test-runner.out.json"
else
  jq '{status,reason}' "docs/$TASK/test-runner.out.json"
  # Enter the existing scoped repair budget below.
fi
```

Require SUCCESS, `.results.failed == 0`, and actual test evidence; SKIP does not
prove tests green. Keep test reports outside the implementation agent firewall.
Initialize `GATE_ATTEMPT=1` separately for each gate. On a failed gate, record the
attempt in its existing persisted retry ledger, increment `GATE_ATTEMPT`, and pass
it on the next scoped repair dispatch. Resume from the recorded count, never reset
an exhausted ledger. Attempt 4 must not be dispatched: the router rejects it.
Automatic gear selection raises capacity on attempts 2 and 3 without an extra
model call; it does not replace the gate or authorize bypassing review/security.

On failure: inspect output in the orchestrator, dispatch a scoped repair using
only permitted feedback, and re-run. After **3 failures on the same test**, stop.

- **Supervised:** escalate to the engineer — do not attempt a 4th fix.
- **Autonomous:** spend the retry budget, then exhaust:
  ```bash
  N=$(bash ~/.nightshift/scripts/nightshift-retry-increment.sh "$TASK" RETRY_IMPLEMENT | tail -1)
  if [ "$N" -ge 3 ]; then
    bash ~/.nightshift/scripts/nightshift-retry-exhaust.sh "$TASK" implement "3 build failures on the same test"
    # return Step 9 contract status:"FAIL"
  fi
  ```

---

## Step 8.5 — Ticket-scoped E2E (Playwright, if any)

If this ticket added Playwright specs, run **only those** here — proving the feature this
ticket built works end-to-end. This is intentionally narrow: the full-suite regression run is
`/nightshift-qa`'s job, and the live-URL smoke is `/nightshift-deploy`'s. Zero-cost when the project has no
Playwright (`nightshift-pw.sh` returns `PW_SKIPPED` → treated as pass).

```bash
# Playwright specs among THIS ticket's Files to Change (sealed in the RED phase).
PW_SPECS=$(grep -E '^\| `[^`]+`' "$SPEC" | sed -E 's/^\| `([^`]+)`.*/\1/' \
  | grep -E '\.spec\.(t|j)sx?$|/e2e/|/tests?/.*\.spec\.' || true)

DETECT=$(bash ~/.nightshift/scripts/nightshift-pw.sh "$TASK" --detect | grep -oE 'PW_PRESENT: (true|false)')
if [ "$DETECT" = "PW_PRESENT: true" ] && [ -n "$PW_SPECS" ]; then
  # Pass the ticket's spec paths as the run target (space-joined glob).
  ONLY=$(echo "$PW_SPECS" | tr '\n' ' ' | xargs)
  E2E=$(bash ~/.nightshift/scripts/nightshift-pw.sh "$TASK" --run --only "$ONLY" --label impl-e2e)
  echo "$E2E"
  # PW_FAIL here is a build failure: the feature's own E2E does not pass. Fix within scope and
  # re-run (supervised), or fold into the retry budget exactly like a unit-test failure (autonomous).
else
  echo "Ticket-scoped E2E: none (no Playwright specs in this ticket's Files to Change)."
fi
```

---

## Step 9 — Autonomous JSON return contract

**Autonomous only.** The final output of this stage must be a single JSON object (no prose) so
`/nightshift-batch` drives on `status` instead of parsing text:

```json
{
  "status": "SUCCESS|FAIL|SKIP",
  "reason": "<required on FAIL and SKIP>",
  "attempts": 1,
  "artifacts": { "branch": "<branch>", "diff": "<summary>" },
  "rules_fired": ["<rule>", "..."]
}
```

- `SUCCESS` — tests green; orchestrator proceeds to `/nightshift-review`.
- `FAIL` — gate failed after retry budget; orchestrator records the ticket failed.
- `SKIP` — terminal non-failure (e.g. already-fixed-upstream); orchestrator records skipped.

Missing/unparseable JSON is treated as `FAIL` with `reason:"malformed agent output"`.
**Supervised mode returns prose, not JSON.**

---

## Step 10 — Hand off

When all ACs are met and tests are green, check off the progress file and (supervised) print:

```
## Implementation complete — <task-key>
### What was built  [2–3 sentences]
### Files modified   [table]
### Tests  ✅ green   ### TDD locks  spec=<sha> red=<sha>
### Next  /nightshift-review <task-key>
```

**Do not commit the final diff. Do not push. Do not open a PR.** The RED-lock commits are the
only commits this stage makes; the GREEN diff stays in the working tree for `/nightshift-review`.

---

## Rules
- No spec = no build (hard stop).
- RED before GREEN, always. red-lock before any fix code.
- Never let the GREEN agent see the test source (firewall).
- Never commit the final diff / push / open a PR.
- Three failures on the same test = escalate (supervised) or exhaust (autonomous) — not a 4th guess.
