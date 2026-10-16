# Task 138 implementation

The dashboard presents a task before request setup, with six selectable stages, recorded next action, existing admitted Resume control and pending questions above stage evidence. Selection is inspection only and survives polling without changing focus. Evidence projection binds routes, artifacts and retained attempts to the selected task/stage. Missing routes remain unknown; historical failures, stale state and unvalidated diagnostics remain labeled. Task-wide evidence is separate. Controller completed-stage receipts remain visible even when no attempt is present.

The change uses the existing React, CSS and esbuild implementation. Nine declared files changed, including three sealed test files and two rebuilt bundles. Server/API contracts, request bodies and authorization bindings are preserved. Completed, pending-acceptance, read-only, active and exhausted states retain disabled controls. Activity copy identifies recorded snapshots rather than verified liveness.

## Automated verification

- Model suite: 24 passed, zero failed; routed test runner independently executed the same suite.
- Production build: successful and reproducible; distribution HTML bytes unchanged.
- Intake browser: Markdown and qualified GitHub requests passed, including missing-choice disclosure, preview identity, zero provider calls during preview/preparation and reciprocal busy locks.
- Control-room browser: six-stage selection, Enter/Space/Tab/Shift+Tab, selected semantics, polling focus, stage/task isolation, historical/missing routes, unsupported actions, desktop/mobile overflow, computed text/control contrast and 44 CSS pixel targets passed at 1440×1000 and 390×844.
- Operations browser: existing evidence/admission journey passed, including retained questions, manual-acceptance fixture, failed verification, retry exhaustion and external adoption. Synthetic acceptance in that disposable fixture does not accept task 138.
- Additional admission probe: task/token/hash/question binding, prominent pending questions, completed/pending acceptance restrictions and read-only state passed with intercepted synthetic requests and zero actual workers.
- Real-task observation: task 138 appeared before request setup at both widths using the checkout-local candidate and retained controller response. No POST requests occurred. This is automated observation, not operator testimony.
- Scoped diff, unchanged locked tests and retained hashes passed.

`implementation-check.json`, `proof-red.json`, `proof-final.json`, `final-proof-record.json` and `proof-check.json` retain the checks. Browser reports/screenshots are under `browser-evidence/`; real-task response and observations have separate provenance. Additional representative screenshots cover running, failed/historical, missing, completed, read-only and pending-question states at both widths. Image inspection informed moving the existing primary control above long evidence.

## Retained failures and repairs

The initial RED model run produced 23 passes and one relevant assertion failure. Spec lock: `52b00e7`; RED lock: `7dd9652`. Before integration, the new browser assertion also observed zero stage buttons on the unpatched UI. Both failures are retained.

The routed author returned a successful read-only proposal with malformed unified hunk framing. Initial integration attempts failed and model checks still failed on unchanged source. The original proposal is preserved. Standard hunks were reconstructed from exact old/new blocks, checked and applied without changing intended content. The subsequent model suite passed.

The first integrated browser run found hidden failed-attempt details and missing-route labels inconsistent with the evidence contract. One source repair opened failed attempts and made missing provider/model labels explicit. The next browser run passed. Source inspection also retained completed-only receipts, and image inspection moved the existing admitted primary action and pending questions above long evidence. Final affected checks passed.

The first proof-check helper incorrectly expected pending manual case C-6 in the failed-case field. Its script/log are retained; the repaired assertion checks the pending scenario field and an empty failed-case list. It passes. No proof policy, scenario, locked test, allowance or counter was weakened/reset.

## Remaining obligations

Required operator visual acceptance C-6 remains pending. The final proof gate returns `manual_acceptance_pending` and `operator_verify_manual_acceptance`; it is not represented as passed. Final deterministic evidence is current, with no failed automated cases.

C-7/AC-6 coverage here is limited to genuine implementation receipts, locks, failed attempts and proof evidence. Review, Drift, QA and branch/PR delivery remain controller-owned. No later-stage receipt, publication, merge or deployment was produced. The working source/bundle diff remains uncommitted.

MEX context used: `.mex/AGENTS.md`, `.mex/ROUTER.md`, `.mex/context/architecture.md`, `.mex/context/conventions.md`, `.mex/patterns/INDEX.md`. Graph impact was unavailable; direct source reads supplied grounding. The existing task tracker records implementation state and lessons. Scaffold source files were not expanded beyond the approved dashboard scope.

## Implement attempt 2 — read-only browser regression

The allowance disclosure now opens by default so the existing continuation control remains accessible. Read-only disabling and request admission are unchanged. Stage and attempt receipt labels now identify their paths explicitly, resolving the existing broad receipt locator without changing its assertion.

The original timeout and the subsequent duplicate-label failure are retained in `read-only-before-implement-2.log` and `read-only-after-implement-2.log`. `read-only-final-implement-2.log` passes the unchanged HTTP/browser regression, including rejected read-only mutations, disabled controls, retained state, desktop/mobile screenshots and no page errors. The existing locked tests remain unchanged. `implementation-check-2.json` and `proof-final-implement-2.json` bind the final source and rebuilt bundle; earlier evidence and receipts remain retained. Manual acceptance C-6 remains pending.
