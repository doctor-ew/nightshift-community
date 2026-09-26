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
last_updated: "2026-09-26"
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

Bounded continuation: new instrumented tickets have a persisted 600-second wall deadline. Explicit operator continuation retains history and call limits while granting at most 600 additional seconds; ordinary resume does not renew time. Portal exposes read-only remaining budget. Sources: `scripts/nightshift-ticket-budget.py`, `scripts/nightshift-continue.sh`, `docs/ten-minute-continuation-20260923.md`. Stub termination verified; ten-minute live completion unproven.

Issue 49 convergence: existing drafts go to missing validation; writer repairs require a current finding brief. Source review reuses accepted unchanged positive reports, rejects unchanged failures, and records repeated explicit conflicts. Claude extraction uses isolated read-only context. Two bounded live synthetic samples passed fault/repair/reuse; isolated usage was 26,499 vs 83,763 tokens, not an end-to-end latency guarantee. Sources: `scripts/nightshift-review-reuse.py`, `scripts/nightshift-spec-repair-brief.py`, `docs/issue-49-convergence-verification.md`. Local implementation; issue 49 remains open for full workflow verification.

Console recovery checkpoints: policy and all recovery routes are resolved before admission. Successful steps are hash-bound and resumed without repeating diagnosis/review; deadlines and attempts persist. Final manual acceptance remains pending even after process success. This is console recovery only, not a full factory state-machine migration. Sources: `scripts/nightshift-recovery-state.py`, `tests/test-console-repair.py`, `docs/controller-recovery-verification-20260923.md`.

Controller review candidate: `scripts/nightshift-pipeline.py` selects single-ticket stages from durable receipts and existing decisions; `scripts/nightshift-handoff.py` bounds optional graph source context. `tests/test-pipeline.py` covers real shell dispatch to synthetic providers, failed-evidence resume, retained deadline/calls, and pending manual acceptance. `scripts/nightshift-jev-evaluation.py` has a labelled public corpus; the local service measurement is unavailable without credentials and reports zero avoided calls. These changes are not installed; batch, legacy review import, readiness and live delivery acceptance remain incomplete. Source: `docs/controller-integration-20260923.md`.

Controller follow-up: existing drafts pass deterministic validation without author dispatch; scoped publication is verified against a local Git remote and rejects unrelated staged changes. Stage retry admission reuses the existing infrastructure/substantive accounting helper. Five controller regressions pass. Sources: `scripts/nightshift-pipeline.py`, `tests/test-pipeline.py`, `docs/controller-integration-20260923.md`. This remains a review candidate, not the activated runtime.

Accepted architecture candidate (#58): `scripts/nightshift-architecture.py` stores explicit operator-accepted, upstream-linked project decisions in common Git state; Beads mirrors references and MEX remains supplemental source retrieval. The controller independently executes scoped path/literal checks after workers, retains findings and budgets, and the existing ticket UI shows decisions and results. `tests/test-architecture.sh` includes cross-worktree next-ticket regression and existing controller tests. This is a draft implementation, not an installed runtime or semantic-model acceptance. Operation and limitations: `docs/architecture-decision-usage.md`.

MEX init integration: `scripts/nightshift-mex.py` prepares the CLI and graph during `scripts/nightshift-init.py`, within a configurable 60-second default allowance. Existing fresh graphs are reused; incompatible graphs remain untouched. `tests/test-mex-init.py` covers lifecycle selection and init integration; live small-repository init/repeat left a clean checkout. See `docs/architecture-decision-usage.md` for measured timings and package-install limits.

Bounded semantic recovery candidate: controller authorization, hashes, test results and budgets remain deterministic. `scripts/nightshift-decision-engine.py` evaluates compact mapped obligations with durable cache validation and selective independent review; `scripts/nightshift-recovery-decisions.py` enforces complete evidence selection before authorization. CLI/browser share the recovery controller. Synthetic regression evidence and rollout limits: `docs/DECISION-RECOVERY.md`, `docs/DECISION-VALIDATION.json`. Not installed or live-model certified.

Composable operations review candidate: `scripts/nightshift-operations.py` provides independently authorized Groom suboperations, implementation, external adoption, deterministic verification, independent review and explicit acceptance/publication. The factory recipe uses the same executor; old ledgers are retained unchanged. Contract and synthetic validation: `docs/operations/CONTRACT.md`, `tests/test-operations.py`, `tests/test-operation-review-regressions.py`. This candidate is not installed or live-certified.

Operation browser regression: `tests/test-operation-browser.py` launches a temporary synthetic repository and home; `dashboard/test-browser.mjs` exercises the built dashboard with pinned headless Chromium and compares CLI results. It covers acceptance, replay, drift, external adoption, verification failure and desktop/mobile rendering. Evidence: `docs/operations/BROWSER-VALIDATION.json`; live providers and installed-runtime rollout remain separate.


Bounded operation repair candidate: explicitly repair-authorized factory/Groom
recipes use `scripts/nightshift-operation-supervisor.py` over the shared executor.
Failed test evidence remains hash-bound, replay preserves request identity and
usage, and changed external adoption can Verify/Review after exhaustion without
Implement. Synthetic evidence and limitations: `docs/operations/BOUNDED-REPAIR.md`.
Not activated or live-provider certified.

Supervisor retry admission follow-up: `scripts/nightshift-operation-supervisor.py`
uses `Operations.execute` to reserve existing retry accounting only after authority
validation. Exhausted/unknown retained requests stop before workers; success and
crash replay finalize once. Evidence: `docs/operations/RETRY-ADMISSION.md` and
`tests/test-operation-supervisor-admission-review.py`. Synthetic only; not activated.
Work-package composition: `scripts/nightshift-work-packages.py` validates versioned
graphs and templates; `scripts/nightshift-package-controller.py` composes shared
operations with isolated child repositories, retained allocations, inherited
accepted architecture, and explicit parent integration. CLI and browser use the
same controller. `tests/test-work-packages.sh` covers deterministic and independent
controller regressions; `dashboard/test-packages-browser.mjs` exercises synthetic
browser composition. Status and remaining acceptance gaps:
`docs/operations/WORK-PACKAGES.md`. No live certification or activation is implied.

Autonomous package preparation: version 3 inline artifacts use
`scripts/nightshift-package-bundle.py` for bounded disposable validation; existing
Groom authority writes only the parent specification artifact. Independent challenge
receives schema-bound child evidence. `scripts/nightshift-package-controller.py`
retains preparation wall phases and evidence coverage before allocating parent wall
time. Evidence and boundaries: `docs/operations/PACKAGE-AUTHORING.md`.

Optional stage-bound semantic handoffs use complete mapped preparation/review evidence and the existing durable decision engine. Jev remains optional and has no authorization or scheduling authority. Sources: `scripts/nightshift-operation-decisions.py`, `scripts/nightshift-decision-engine.py`, `tests/test-semantic-handoffs.py`, `docs/operations/SEMANTIC-HANDOFFS.md`. Synthetic control-flow evidence does not establish live accuracy or savings.
Package composition wall follow-up: later authorizations, including a different operator or graph binding, cannot exceed the earliest retained composition deadline. Idle before the first composition authorization retains the active preparation policy. Sources: `scripts/nightshift-package-controller.py` (`Packages.authorize`), `tests/test-package-composition-window-review.py`, `docs/operations/COMPOSITION-WINDOW.md`. Synthetic evidence only; no live activation.

Guided intake uses `scripts/nightshift-intake.py`, `dashboard/src/intake.jsx` and the shared operation API to preview and prepare bounded plans without provider calls. Source snapshots, unresolved nonexecuting decisions, current-file receipts and serving/installed identity remain explicit. Tests: `tests/test-intake.sh`, `tests/test-intake-browser.py`. Boundaries: `docs/operations/GUIDED-INTAKE.md`.

Semantic cache identity follow-up: evaluator/mapper/configuration-adapter/transport source hashes bind semantic authority and are revalidated with the current task, policy and route. Changed code requires fresh calls within retained budgets; old receipts cannot be relabeled. Sources: `scripts/nightshift-operation-decisions.py`, `tests/test-semantic-cache-review.py`, `docs/operations/SEMANTIC-CACHE-IDENTITY.md`. Other typed mapping acceptance remains open.

Intake namespace follow-up: bare GitHub references must match independently derived project-origin identity; qualified references retain explicit repository selection. Existing input/context and journal safeguards remain. Sources: `scripts/nightshift-intake.py`, `tests/test-intake-namespace-review.py`, `docs/operations/INTAKE-NAMESPACE.md`. Synthetic evidence only; no runtime activation.
