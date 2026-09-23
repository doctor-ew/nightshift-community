---
name: router
description: Session bootstrap and navigation hub. Read at the start of every session before any task. Contains project state, routing table, and behavioural contract.
edges:
  - target: context/architecture.md
    condition: when working on system design, integrations, or understanding how components connect
  - target: context/stack.md
    condition: when working with specific technologies, libraries, or making tech decisions
  - target: context/conventions.md
    condition: when writing new code, reviewing code, or unsure about project patterns
  - target: context/decisions.md
    condition: when making architectural choices or understanding why something is built a certain way
  - target: context/setup.md
    condition: when setting up the dev environment or running the project for the first time
  - target: context/proof-accounting.md
    condition: when diagnosing proof admission or accounting
  - target: context/updates.md
    condition: when changing releases or repairing installations
  - target: patterns/INDEX.md
    condition: when starting a task — check the pattern index for a matching pattern file
last_updated: "2026-09-23"
---

# Session Bootstrap

If you haven't already read `AGENTS.md`, read it now — it contains the project identity, non-negotiables, and commands.

Then read this file fully before doing anything else in this session.

## Current Project State
**Working (implementation/fixture evidence, not live deployment certification):**
- Explicit workshop profile runs bounded, fresh safe-mode Claude stages with a file ledger and spec approval; fixture coverage includes costs, timeouts, resume, repairs, and dashboard receipts. Live macOS subscription pilot passed eight public cases in 198.3 seconds and 43,793 tokens; Windows/API-key certification remains unverified. Sources: `scripts/nightshift-workshop.py`, `tests/test-workshop.py`, `docs/WORKSHOP.md`.
- Explicit `nightshift init` prepares configuration and a committed Git baseline without starting a model. Sources: `scripts/nightshift-init.py`, `tests/test-init.py`.
- Configurable concise/verbose/quiet output retains private runtime logs; explain distinguishes briefs from audits. Sources: `scripts/nightshift-output.py`, `tests/test-output.py`, `commands/nightshift-explain.md`.
- Optional advice, explanation, architecture/UX planning, and BMad artifact guidance are exposed across runtime adapters. Sources: `commands/nightshift-help.md`, `scripts/nightshift-factory.sh`, `tests/test-factory-cli.sh`. See `patterns/change-cli-runtime.md` for boundaries.
- CLI runtime/model shorthand and configurable local aliases are regression-covered (`scripts/nightshift-factory.sh` (line 122), `tests/test-factory-cli.sh` (line 1)). See `patterns/change-cli-runtime.md` for precedence and fixture boundaries.
- Runtime-neutral stage flow is documented in the setup brief's README excerpt.
- Proof budget validation and admission exist (`scripts/nightshift-retry-budget.py` (line 139)).
- Release selection and guarded updates exist (`scripts/nightshift-update.py` (line 44)).
- Strict trajectory validation and replay exist (`scripts/nightshift-trajectory.py` (line 42), `evals/trajectory/replay.py` (line 16)).

**Not Built / not established:**
- Fresh-machine independently reviewed end-to-end beginner validation remains required (setup brief, README excerpt).
- [TO DETERMINE] actual unbuilt feature backlog; no authoritative backlog was supplied.
- [TO DETERMINE] promoted support for local-model upgrades and ACP; brief labels these experimental.

**Known Issues / evidence limits:**
- Brief manifest and tooling fields are null; do not invent build/lint commands.
- Dirty/development checkout update deferral is regression-covered (`tests/test-release-inputs.py` (line 48)).
- Adapter repair failure retains pending work (`tests/test-release-inputs.py` (line 89)).
- Original decision dates, considered alternatives, and complete adapter environment requirements remain [TO DETERMINE].

Source inventory: `.mex/local/setup-population-raiHOV/prompt.md`; implementation claims are expanded in grounded domain files. Metadata dates record scaffold maintenance, not historical decision dates.

Workshop evidence update: `source-integrity-v1` separates supplied citations from verified claims and preserves synthetic labels. Final review receives cases and raw observations; an invalid test oracle stops before prompt repair. Earlier exercise caches are not upgraded in place. Sources: `scripts/nightshift-workshop.py` (`EVIDENCE_POLICY`, `Run.reviewed`, `Run.workflow`), `docs/WORKSHOP.md`.

Workshop runtime follow-up: reviews consume Claude schema-constrained `structured_output`; malformed JSON reports stage and raw receipt path. Failed workshop agent cards surface the gate reason. Sources: `scripts/nightshift-workshop.py`, `dashboard/src/app.jsx`, `docs/WORKSHOP.md`.

Workshop recovery: `--retry-review` allows one malformed final-review retry after drift validation, retaining failure snapshots, call receipts and original budgets. Semantic gate failures are not eligible. Source: `scripts/nightshift-workshop.py` (`Run.recover_review`), `docs/WORKSHOP.md`.

Review-branch implementation, not activated in the installed runtime: `quoted-evidence-v2` requires complete case/requirement assessment matrices and exact response quotations for grader and independent final review. Execution completion is distinct from verification; unresolved evidence never passes. Source: `scripts/nightshift-workshop.py` (`validate_assessments`, `Run.reviewed`), `tests/test-workshop-evidence.py`, `docs/WORKSHOP.md`.

Quoted-evidence rollout gate: 36 offline checks pass, but three live reviewer probes timed out with no verdict. Live verification remains blocked; runtime stays at the prior tested implementation. Source: `docs/WORKSHOP-QUOTED-EVIDENCE-VALIDATION.json`.

Quoted-evidence follow-up: standard 90-second targeted live regression passed after earlier timeouts; known bad evidence rejected and positive control accepted. Installed runtime updated to the tested contract. No full fresh workshop or Windows verification is claimed. Source: `docs/WORKSHOP-QUOTED-EVIDENCE-VALIDATION.json`.

Local convergence guard: the bounded source dispatcher refuses unchanged registered repair inputs after a substantive review failure, without another reservation. Dashboard admission receipts expose the blocker; they never approve a gate. Source: `scripts/nightshift-retry-budget.py` (`repair_admission`), `tests/test-repair-dispatch.py`, `docs/RETRY-BUDGETS.md`. Live model completion remains unverified.

Portal chat routing fix: submission and its background worker use `scripts/nightshift-routing-path.py` instead of requiring an application-local routing file. The admitted routing path is retained privately for the child. Sources: `scripts/nightshift-console-chat.py`, `tests/test-console-chat.py`, `tests/test-routing-path.py`. Chat/routing/HTTP fixtures pass; live provider verification was not performed.

Decision reuse is enforced by `scripts/nightshift-console-decisions.py`: repeated normalized questions or stable `decision_key` values return the existing answer. Explicit reopening requires the latest answered hash and a reason. Tests: `tests/test-console-decisions.py`. This does not infer equivalence for differently worded legacy questions without keys or approve gates.

## Routing Table

Load the relevant file based on the current task. Always load `context/architecture.md` first if not already in context this session.

| Task type | Load |
|-----------|------|
| Understanding how the system works | `context/architecture.md` |
| Working with a specific technology | `context/stack.md` |
| Writing or reviewing code | `context/conventions.md` |
| Making a design decision | `context/decisions.md` |
| Setting up or running the project | `context/setup.md` |
| Proof budgets and admission | `context/proof-accounting.md` |
| Release selection and installation repair | `context/updates.md` |
| Any specific task | Check `patterns/INDEX.md` for a matching pattern |

## Behavioural Contract

For every task, follow this loop:

1. **CONTEXT** — Load the relevant context file(s) from the routing table above. Check `patterns/INDEX.md` for a matching pattern. If one exists, follow it. Narrate what you load: "Loading architecture context..."
2. **BUILD** — Do the work. If a pattern exists, follow its Steps. If you are about to deviate from an established pattern, say so before writing any code — state the deviation and why.
3. **VERIFY** — Load `context/conventions.md` and run the Verify Checklist item by item. State each item and whether the output passes. Do not summarise — enumerate explicitly.
4. **DEBUG** — If verification fails or something breaks, check `patterns/INDEX.md` for a debug pattern. Follow it. Fix the issue and re-run VERIFY.
5. **GROW** — After meaningful work, run this binary checklist:
   - **Ground:** What changed in reality? Name the changed behavior, system, command, dependency, or workflow.
   - **Record:** If project state changed, update the "Current Project State" section above. If documented facts changed, update the relevant `context/` file surgically.
   - **Orient:** If this task can recur and no pattern exists, create one in `patterns/` using `patterns/README.md`, then add it to `patterns/INDEX.md`. If a pattern exists but you learned a gotcha, update it.
   - **Write:** Bump `last_updated` in every scaffold file you changed. If the why matters, run `mex log --type decision "<what changed and why>"` or `mex log "<note>"`.

Manual external acceptance: required manual cases now preserve AC coverage while permitting development after automated evidence. Final completion stays blocked pending operator verification; manual attestation ingestion is not implemented. Historical portal failures are labelled as recorded evidence. Sources: `scripts/nightshift-behavior-proof.py`, `tests/test-manual-acceptance.py`, `docs/manual-acceptance-verification-20260923.md`. Local verification only; IF-325 has not been migrated or resumed.
