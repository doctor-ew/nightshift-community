# 138 — Nightshift control-room dashboard

> AIRLOCK BYPASSED: no supplemental PRD. The authoritative issue and controller handoff define scope. Product sign-off, behavioral proof, manual acceptance, later stages and publication remain pending; independent classification review is retained by Product.

## Problem
Issue 138 requires a focused dashboard for inspecting a task and taking its recorded next useful action, building on the intake simplification identified as PR #137 [S1]. The current render places tickets before request setup, but stages are noninteractive list items and controller routes occupy a separate disclosure [S2].

## Technical Constraints
Use the existing React/CSS and esbuild stack; introduce no UI framework [S3]. Limit implementation to dashboard presentation, model, tests and generated distribution assets. Preserve intake and server admission/API contracts.

Keep the six recorded stages in order: product, adversarial, implement, review, drift, qa. Preserve controller precedence, stale recovery revalidation, missing evidence and historical failures [S4]. Selection is inspection only.

Preserve existing action tokens, evidence bindings, completed/read-only restrictions, pending decisions, active-work locks and exhausted retry/call allowances [S5, S6]. Preserve preview/prepare/execute separation, automatic missing-choice disclosure and reciprocal intake/operations busy locks [S7, S8].

Operational requirements from the authoritative ticket [S1]: isolated worktree and checkout-local runtime; preserve the pinned talk runtime, completed rehearsal fixture, receipts/budgets, running talk dashboard, slide decks, global installation and unrelated handoff_20260907.md. Use subscription authentication, gear 1 and configured independent author/reviewer routing. Keep Jev disabled and Hermes deferred. No merge, deployment, permanent deletion, budget resets or silent allowance renewal. Maximum three in-scope repair attempts per failing gate. GitHub remains authoritative; Beads is local only.

This Product worker returns a two-file proposal patch. Implementation, later stages, browser journeys and publication belong to the controller.

## Solution Design
Deliver one cohesive dashboard experience. Stage inspection, task actions and evidence hierarchy share task identity and one presentation model; sequential verification/publication obligations do not justify separate product child tickets. Do not recursively invoke the factory.

Place task identity, recorded status, the six-stage selector, recorded next useful action and pending questions before request setup. Display the controller's recorded next action with existing admitted controls. Unknown or unsupported actions receive explanatory read-only text, never invented execution buttons. Keep existing controls accessible under their existing admission rules.

Use native buttons in a labeled stage navigation group. Each exposes aria-pressed, with exactly one selected stage per task and an associated labeled evidence section. Tab/Shift+Tab traverses stages in order; Enter/Space selects. Arrow-key tab behavior is not required for this button-group contract. Initially select a recognized recorded current stage, otherwise the first stage; selection never implies passage. Retain selection across polling without moving focus. Changing task identity must not retain another task's evidence.

### UI-E1 — canonical UI evidence contract
The selected stage's detail area contains, in order:
1. Selected task/stage identity and recorded state.
2. Recorded provider/model.
3. Artifacts.
4. Tests and proof/receipts.
5. Retained attempt history.

Bind every record to the selected task and stage using explicit existing provenance. Each attempt keeps its own route/outcome; failures remain accessible after later success. Task-wide links without stage provenance belong in a separately labeled task-evidence subsection. Missing provider, model, tests, proof or receipts receive explicit not-recorded labels. A recorded pass is not a new test run, and a receipt path does not mean this UI verified its contents. Preserve stale/unvalidated labels. Never substitute configured routing defaults for recorded routes. Existing attempt routes/receipts and task artifact links are displayed by the current UI [S5]; no backend fields are added.

Prompts, scenarios, tests and review reference UI-E1 rather than competing evidence schemas. Usage, lifecycle history and diagnostics remain reachable through secondary disclosures. Preserve unknown usage rather than zero, historical failures rather than success-only history, and recorded process state rather than inferred heartbeat [S9]. Qualify progress copy so missing/stale snapshots cannot establish liveness [S10].

At 1440x1000 and 390x844, long task identifiers, routes and evidence paths wrap. Stage navigation may wrap; local evidence scrolling must remain within the viewport and expose focused content. No horizontal page overflow. Every control/disclosure has visible keyboard focus; status uses text beyond color. Require 4.5:1 normal-text contrast, 3:1 large-text/control-boundary contrast and stage/action controls at least 44 CSS pixels high. These are acceptance requirements, not claims that existing CSS proves them [S11].

## Files to Change
| File | Change | Why |
|---|---|---|
| `dashboard/src/app.jsx` | Task-first control room, stage selection and UI-E1; preserve existing action handlers | AC-1, AC-2, AC-3 |
| `dashboard/src/model.mjs` | Pure task/stage evidence projection with provenance and explicit missing data | AC-2, AC-3 |
| `dashboard/src/app.css` | Responsive stage/detail layout, focus, wrapping and contrast | AC-2, AC-5 |
| `dashboard/src/ticket-live.jsx` | Qualify recorded activity and missing snapshot copy; preserve question/action contracts | AC-1, AC-3 |
| `dashboard/test-model.mjs` | TEST: Stage isolation, historical/missing evidence and admission regressions | AC-2, AC-3, AC-5 |
| `dashboard/test-intake-browser.mjs` | TEST: Preserve both intake journeys/locks; add stage and responsive regressions with labeled synthetic ticket fixtures | AC-1, AC-2, AC-3, AC-4, AC-5 |
| `dashboard/test-browser.mjs` | TEST: Preserve operations/manual-acceptance journey and assert state boundaries | AC-3, AC-5 |
| `dashboard/dist/assets/app.js` | Rebuild generated production JavaScript | AC-5 |
| `dashboard/dist/assets/app.css` | Rebuild generated production CSS | AC-5 |

Nine rows. No server, runtime, dependency or intake authorization changes. The build also copies its HTML entry; preserve identical HTML bytes rather than introducing an unused scope row [S3, S12]. Controller stage receipts/publication evidence are delivery artifacts, separate from implementation source scope.

## Acceptance Criteria
- **AC-1:** GIVEN a real retained controller task, WHEN opening the dashboard, THEN that task precedes request setup with its current recorded status and six-stage pipeline. Synthetic fixtures test rendering but cannot satisfy the real-task obligation.
- **AC-2:** GIVEN recorded, missing, historical and stale stage evidence, WHEN selecting a stage by pointer or keyboard, THEN UI-E1 changes to that task/stage with honest route/evidence provenance, selected-state semantics and visible focus. Polling retains selection without focus theft; failures remain accessible.
- **AC-3:** GIVEN completed, read-only, running, exhausted, stale or pending-question states, WHEN inspecting/using existing controls, THEN admission, binding and authorization conditions remain intact. Completed/read-only tasks cannot start unauthorized work; admitted pending questions remain answerable through existing controls. Inspection never dispatches.
- **AC-4:** GIVEN Markdown and qualified GitHub request sources, WHEN completing existing browser journeys, THEN automatic missing-choice disclosure, preview identity, preview/prepare/execute separation and bidirectional busy locks still pass.
- **AC-5:** GIVEN the rebuilt candidate, WHEN running focused regressions, dashboard model tests, production build and desktop/mobile browser checks, THEN meaningful stage/state coverage passes and committed distribution assets are rebuilt. Representative states require actual visual inspection; operator acceptance stays pending until recorded.
- **AC-6:** GIVEN the controller-owned workflow, WHEN delivering the change, THEN canonical Product, Adversarial, Implementation, Review, Drift and QA have real retained receipts and required TDD/proof. Preserve failed attempts and scope limitations; deliver a reviewable branch/PR, never merge or deploy. Product authoring alone does not satisfy delivery.

## Capability Matrix
Installed helper capabilities ran before scenario authoring: available, schema version 1. Supported operators: text_equals, text_contains, text_section_contains, json_equals, json_field_equals, json_field_length_at_most, json_field_nonempty. Discovery is neither approval nor observed behavior.

| AC | Observable artifact | Supported check | Semantic obligation | Unresolved dependency |
|---|---|---|---|---|
| AC-1 | Rendered task order/status and retained controller response | Browser DOM/order assertions and response comparison | Genuine retained-task provenance | Later retained-task capture; fixtures insufficient |
| AC-2 | Selected UI-E1 and accessibility state | Model equality and browser role/focus/aria-pressed/content assertions | Correct task/stage attribution and honest history | New regressions pending |
| AC-3 | Disabled controls and captured authorized requests | Admission matrix and network assertions | No weakened authority or inferred completion | Later controller boundary verification |
| AC-4 | Intake report and observed requests | Existing browser journey assertions | Preparation/execution separation | Browser execution pending |
| AC-5 | Test/build logs, bundles, screenshots, operator observations | Ordinary tests/build and overflow/focus assertions | Visual hierarchy, contrast and usability review | Browser environment and operator acceptance pending |
| AC-6 | Six-stage receipts, proof and branch/PR evidence | Controller receipt/schema/hash/status checks | Authentic independent review; honest failed/unknown evidence | Later stages/publication pending |

Containment cannot prove DOM order, stage cardinality, authorization, visual quality or real retained execution. The text oracle is not a browser harness. No model prototype runtime is required. Missing required browser/manual/controller evidence blocks its acceptance obligation rather than becoming not applicable.

## Risks
Cross-stage fallback can fabricate routes. Polling can reset selection or steal focus. Success-only rendering can erase failures. Responsive layouts can clip controls or overflow. Synthetic evidence can be mistaken for real delivery. UI-E1, public counterexamples and separate provenance address these risks.

## Dependencies
Controller must confirm the PR #137 baseline relationship before implementation; this worker read current intake behavior, not PR ancestry [S1, S7].

The installed validator supports required manual cases although the installed prose schema overview lists earlier classifications. Its manual contract was read and the proposed artifact validated against the installed helper [S13]. No private fixtures were read; no held-out runtime applies.

MEX graph was absent; its optional capability probe encountered a read-only cache permission error. Direct reads supplied grounding. MEX context used: .mex/AGENTS.md, .mex/ROUTER.md, .mex/patterns/INDEX.md, .mex/context/stack.md, .mex/context/conventions.md. The read package manifest supersedes scaffold tooling gaps.

## Test Plan
Canonical public scenario semantic SHA-256: `10d8f66ac2a30ed9714b9e45f600b400603d31a6ea3b442fbf506ab00dd4058a`.

Hash canonical UTF-8 JSON with sorted keys, compact separators, non-ASCII preserved and nonfinite numbers rejected; normalize only top-level and case applicability.review to null [S14]. Scenarios contain no spec digest, avoiding circularity. Installed schema validation passed in memory. Scope-table parsing passed using the existing parser's read-only AWK portion without activating a lease [S20]. Review fields start null and are populated only from retained independent approval bound to the current semantic digest. The author claimed no executed UI test, retained-task observation or operator attestation; actual classification approval is retained separately by Product.

| Case | AC coverage | Required evidence |
|---|---|---|
| C-1 | AC-1 | DOM-order regression plus later real retained-task observation |
| C-2 | AC-2, AC-5 | Multi-task/stage isolation, history and selection assertions |
| C-3 | AC-3, AC-5 | Admission matrix, disabled controls and request/dispatch observations |
| C-4 | AC-4 | Both source journeys, missing choices and both lock directions |
| C-5 | AC-2, AC-5 | Model tests, production build, keyboard/overflow checks and rebuilt bundles |
| C-6 | AC-1, AC-5 | Required manual visual/retained-task inspection; pending actual testimony |
| C-7 | AC-6 | Later stage receipts, proof, failed attempts and branch/PR evidence |

Controller execution sequence:
1. Integrate proposal, confirm baseline, finish Product sign-off and independent classification/adversarial review. Do not infer admission from this author result.
2. Implementation records relevant assertion-failing RED for new behavior, locks tests and records actual focused/final passing evidence under existing proof gates. Syntax/import failure is not RED. No extra model prototype gate.
3. From dashboard run `npm test` and `npm run build`. From repository root run `python3 tests/test-intake-browser.py` and `python3 tests/test-operation-browser.py` [S3, S15, S16]. New stage assertions run through the scoped browser files. Retain exact logs/outcomes and rerun affected gates after repairs.
4. Capture 1440x1000 and 390x844 browser assertions/screenshots for running, failed/historical, missing, completed, read-only, pending-question and long-content states. Synthetic reports remain synthetic. Separately observe a real retained task against the checkout-local candidate, retaining task identity, revision and controller response. Do not manipulate the running talk dashboard.
5. For C-6, operator records actual observed result, revision, widths and evidence references through existing manual-acceptance controls. Preserve pending_manual_acceptance until actual acceptance. Screenshots/build success alone are insufficient.
6. Controller completes actual Review, Drift and QA and verifies C-7, including canonical Product/Adversarial/Implementation receipts, TDD/proof, failed attempts and limitations. Receipt presence alone is not success. Retain failed/unknown outcomes, never reset budgets and stop the affected ticket after three authorized in-scope repairs per failing gate. Publish the admitted reviewable branch/PR without merge or deploy.

Public counterexamples reject wrong-stage routes, fixture-only real-task claims, enabled completed-task Resume, preview dispatch, mobile focus loss, fabricated manual testimony and synthetic six-stage receipts. Synthetic manual testimony is never operator acceptance for this task. Existing browser/model coverage provides starting points, not observed passing results [S17-S19].

Initial authoring is not a repair. Subsequent repairs must retain pre-repair artifacts, mandated repair coverage and mechanically checkable regression receipts before paid re-review; allowances are not reset.

## Open Questions
No product ambiguity requires a question. Baseline ancestry, independent review, RED/final evidence, browser execution, real retained-task capture, operator visual acceptance and real stage/publication receipts remain pending gate obligations.

## Model Router
**Decision:** nightshift-architect

Nine Files to Change rows and a presentation/model design decision. Configured routing selects the provider/model at dispatch.

## Sources
Repository baseline: branch nightshift/138, commit 758ba3d. Supplied EXTRACTOR_RUN: 2026-10-15T19:38:00.048261+00:00; extraction result timestamp: 2026-10-15T19:38:04Z; extractor commit 758ba3d. Direct reads support the following facts.

- [S1] `docs/138/source-ticket.json:1-10` (branch: nightshift/138, commit: 758ba3d) — authoritative ticket snapshot, ACs and operational constraints; untracked controller input at this baseline, not claimed committed.
- [S2] `dashboard/src/app.jsx:202-204` (branch: nightshift/138, commit: 758ba3d) — noninteractive stage list.
- [S2] `dashboard/src/app.jsx:304-318` (branch: nightshift/138, commit: 758ba3d) — ticket/request order and secondary disclosures.
- [S3] `dashboard/package.json:1-1` (branch: nightshift/138, commit: 758ba3d) — React/build dependencies and test/build commands.
- [S3] `dashboard/build.mjs:1-6` (branch: nightshift/138, commit: 758ba3d) — production bundle and HTML copy.
- [S4] `dashboard/src/model.mjs:98-128` (branch: nightshift/138, commit: 758ba3d) — six-stage order, controller precedence, stale recovery, task usage identity and continuation admission.
- [S4] `dashboard/src/model.mjs:35-57` (branch: nightshift/138, commit: 758ba3d) — controller/recovery status precedence over historical observations.
- [S5] `dashboard/src/app.jsx:117-188` (branch: nightshift/138, commit: 758ba3d) — ticket fetch, action bindings, read-only state and route/receipt disclosure.
- [S5] `dashboard/src/app.jsx:222-248` (branch: nightshift/138, commit: 758ba3d) — distinct action conditions and task artifact access.
- [S6] `dashboard/src/ticket-live.jsx:73-105` (branch: nightshift/138, commit: 758ba3d) — bound decision submission and existing question controls.
- [S7] `dashboard/src/intake.jsx:3-49` (branch: nightshift/138, commit: 758ba3d) — collapsed details, missing-choice disclosure, preview/apply bindings and preparation conditions.
- [S8] `dashboard/src/operations.jsx:5-14` (branch: nightshift/138, commit: 758ba3d) — combined intake/operations busy state.
- [S8] `dashboard/src/operations.jsx:94-94` (branch: nightshift/138, commit: 758ba3d) — reciprocal busy wiring.
- [S9] `dashboard/src/app.jsx:253-269` (branch: nightshift/138, commit: 758ba3d) — unknown/missing usage presentation.
- [S9] `dashboard/src/app.jsx:313-329` (branch: nightshift/138, commit: 758ba3d) — lifecycle/diagnostic access and caveats.
- [S10] `dashboard/src/ticket-live.jsx:7-31` (branch: nightshift/138, commit: 758ba3d) — progress snapshot and current activity/liveness copy.
- [S11] `dashboard/src/app.css:1-39` (branch: nightshift/138, commit: 758ba3d) — responsive/focus/wrapping and stage-scroll declarations, not measured acceptance.
- [S12] `dashboard/index.html:1-2` (branch: nightshift/138, commit: 758ba3d) — production JavaScript/CSS entry paths.
- [S13] `scripts/nightshift-behavior-proof.py:468-515` (branch: nightshift/138, commit: 758ba3d) — scenario schema and required manual owner/authorization/procedure contract; matching installed validator executed read-only.
- [S14] `docs/BEHAVIOR-PROOF.md:16-65` (branch: nightshift/138, commit: 758ba3d) — stable ACs, classification, null review, canonical digest and no-prototype runtime metadata.
- [S15] `tests/test-intake-browser.py:10-23` (branch: nightshift/138, commit: 758ba3d) — disposable intake browser wrapper.
- [S16] `tests/test-operation-browser.py:16-47` (branch: nightshift/138, commit: 758ba3d) — disposable operation browser wrapper and bounded journey evidence.
- [S17] `dashboard/test-intake-browser.mjs:23-69` (branch: nightshift/138, commit: 758ba3d) — both sources, preview identity, locks, widths and synthetic labeling.
- [S18] `dashboard/test-browser.mjs:37-79` (branch: nightshift/138, commit: 758ba3d) — question, verification, replay and synthetic manual-acceptance journey.
- [S19] `dashboard/test-model.mjs:76-110` (branch: nightshift/138, commit: 758ba3d) — existing pending-stage, usage, controller-precedence and admission assertions; no passing run claimed.
- [S20] `scripts/nightshift-scope-activate.sh:22-36` (branch: nightshift/138, commit: 758ba3d) — deterministic Files to Change parsing, extracted and executed without lease activation.
