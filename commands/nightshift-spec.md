---
name: nightshift-spec
description: "Generate a technical specification from a task or ticket. Auto-detects Story, Bug, or Arcade mode. Delegates to nightshift-spec-writer, which must fill ## Model Router and ## Sources. Read-only — no code, no git state changes. Run /nightshift-spec <task-key>."
argument-hint: "<task-key> [--quick|--full|--force]"
---

# /nightshift-spec — Generate a Spec

Authentication is invocation-scoped: initialize `STAGE_AUTH=subscription` and
set it to `api` only after parsing an explicit `--auth api` in this invocation's
arguments. Remove that option from the ticket key. Never import authentication
authorization from saved state, configuration, or an inherited environment variable.
Forward the explicit option to every nested stage; a resumed run must opt in again.

The spec is the contract for everything downstream. No code without a spec.

> **HARD STOP — THE SPEC PHASE IS READ-ONLY.**
> Do not write code, edit implementation files, or run git commands that change state. The
> phase ends when the engineer approves the spec document. Nothing else.

Normally invoked by `/nightshift-product` Step 7, which supplies ticket content, engineer notes, and
the verification manifest. It also runs standalone.

## Usage

```
/nightshift-spec <task-key>          # auto-detect mode
/nightshift-spec <task-key> --quick  # force Arcade mode
/nightshift-spec <task-key> --full   # force full Story spec
/nightshift-spec <task-key> --force  # regenerate even if a spec exists
```

---

## Step 1 — Resolve paths and check for an existing spec

```bash
STAGE_ARGS=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stage-args.py" "${ARGUMENTS:-$*}") || exit $?
STAGE_AUTH=$(jq -r '.auth' <<< "$STAGE_ARGS")
TASK=$(jq -er '.argv[0] | select(type == "string" and length > 0)' <<< "$STAGE_ARGS") || exit 64
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DIR="${PROJECT}/docs/${TASK}"
SPEC="${DIR}/SPEC.md"
mkdir -p "$DIR"
```

| Condition | Action |
|-----------|--------|
| No spec | Generate |
| Spec exists, task unchanged | Show it: *"Spec is current. Confirm before implementing."* |
| Spec exists, task updated since | *"⚠️ Spec may be stale."* Show what changed, ask: update or proceed? |
| `--force` | Regenerate unconditionally |

**Never silently overwrite an approved spec.**

---

## Step 2 — Assemble the delegation brief

Pass to `nightshift-spec-writer` whatever of these exists. When invoked by `/nightshift-product`, all of it
is already in context — carry it verbatim rather than re-fetching.

- **Ticket content** — resolved title and body, verbatim
- **Ledger metadata** — bead id, external ref, source URL (all optional)
- **Engineer notes** — intent, hidden constraints, blast radius
- **Product spec** — verbatim under `## Product Spec`, if an airlock spec exists
- **Verification manifest** — the full `nightshift-code-fact-extractor` report plus its
  `EXTRACTED_AT` and commit, so Sources entries can be stamped and drift detected later
- **Mode flag** — `--quick` / `--full` if passed

Inject verbatim into the brief:

> **REQUIRED — every spec ends with these two sections:**
>
> **`## Model Router`** — count the Files to Change table:
> - ≥ 3 files OR ≥ 2 top-level modules → **nightshift-architect**
> - Architecture or design decision → **nightshift-architect**
> - Shared contract change (API, DTO, hook signature, stored procedure) → **nightshift-architect**
> - Otherwise → **nightshift-engineer**
>
> Write it filled: `**Decision:** nightshift-engineer`. Name the *role*, never a model — the model is
> resolved at dispatch from `routing.json`. A `[ ]` placeholder is blocked by the guardrail hook.
>
> **`## Sources`** — every file read to support a factual claim:
> `` `repo-relative/path/to/file.ext:120-134` (branch: BRANCH, commit: SHORT_SHA) — what this confirms ``
> Line numbers, branch, and commit SHA all required. `see file` is invalid. The
> `nightshift-spec-guardrail` hook blocks the Write if Sources is absent or has no
> `path:line ... commit:` entries.
>
> Identifiers marked ❌ NOT FOUND in the verification manifest must not appear in the spec body.
> They go under `## Open Questions`.

---

## Step 3 — Delegate

Write the complete brief to `docs/$TASK/spec-writer.in.md` (reuse the product
stage's prepared brief when present). Dispatch once through the shared boundary:

```bash
if bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-agent.sh" \
  nightshift-spec-writer --gear "${GEAR:-${NIGHTSHIFT_GEAR:-auto}}" --auth "${STAGE_AUTH:-subscription}" --risk "${NIGHTSHIFT_RISK:-standard}" --attempt "${GATE_ATTEMPT:-1}" --in "docs/$TASK/spec-writer.in.md" \
  --out "docs/$TASK/spec-writer.out.json"; then
  jq '{status,reason,results,artifacts}' "docs/$TASK/spec-writer.out.json"
else
  jq '{status,reason}' "docs/$TASK/spec-writer.out.json"
  # Stop or use the existing factory repair budget; never fabricate a spec.
fi
```

Require SUCCESS, inspect `.results.spec_path`, and verify the actual SPEC.md and
its evidence gates. FAIL/transport errors preserve the existing block policy;
SKIP does not mean a spec was written. Persist actual successful authorship:

```bash
jq -er 'select(.status == "SUCCESS") | .artifacts.provider' \
  "docs/$TASK/spec-writer.out.json" > "docs/$TASK/spec-author-provider.txt"
```

Codex/local always run read-only. Spec file writes need a separately authorized
integration; missing output files are failures even when the model claims success.

---

## Step 4 — Present for approval

Show the spec. Ask for approval. On approval:

> "Spec approved: `docs/<task-key>/SPEC.md`.
> **Next:** `/nightshift-adversarial <task-key>` to verify its claims."

`/nightshift-spec` does not write the progress tracker — `/nightshift-product` Step 8 owns that, so a
standalone `/nightshift-spec` run leaves no half-initialized pipeline state behind.

---

## Output

`docs/<task-key>/SPEC.md`.

| Mode | Contains |
|---|---|
| **📋 Story** | Problem, Technical Constraints, Solution Design, Files to Change, AC, Risks, Dependencies, Test Plan, Open Questions, Model Router, Sources |
| **🐛 Bug** | Traces To, Current Behavior, Expected Behavior (engineer-defined), Root Cause Hypothesis, AC, Edge Cases, Test Plan, Model Router, Sources |
| **🕹 Arcade** | Problem, Technical Constraints, Files to Change, AC, Model Router, Sources |

Model Router and Sources are required in every mode.
