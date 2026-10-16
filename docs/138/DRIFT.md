## Spec ↔ Implementation Drift

**Task:** 138
**Date:** 2026-10-15
**Base:** 758ba3d (spec-recorded baseline; local `main` is behind it, merge-base 92b5d71, so `main...HEAD` would include unrelated history)
**Changed files:** 9 source files (plus allowlisted `docs/138/*`)

Compared: `git diff 758ba3d` (committed RED-phase tests + working-tree implementation).

---

### Missing Implementation
Spec listed these files; diff doesn't touch them.

| Severity | File | Spec marker | Notes |
|----------|------|-------------|-------|
| — | none | — | All 9 Files to Change rows appear in the diff (MODIFY). Row-set diff against the spec table is empty. |

### Unspecified Changes
Diff touches these files; spec didn't list them.

| Severity | File | Lines changed | Notes |
|----------|------|---------------|-------|
| — | none | — | No server, runtime, dependency or intake-authorization files changed. `dashboard/index.html`, `package.json`, `package-lock.json`, `server.py`, `build.mjs`, `intake.jsx`, `operations.jsx` are byte-identical to baseline. `docs/138/*` is allowlisted. |

### Acceptance Criteria Coverage
| AC | Status | Evidence |
|----|--------|----------|
| AC-1 | COVERED (WARN: manual visual acceptance pending) | `app.jsx` renders `TicketActions` before `WorkshopReviews`/`OperationsPanel`; `test-intake-browser.mjs` asserts task precedes `Guided intake` and six stage buttons. Real retained task observed: `docs/138/real-task-observation.json` (`synthetic:false`, revision 7dd9652) and `real-task-response.json`. |
| AC-2 | COVERED | `model.mjs` `stageEvidence`; `app.jsx` `StageEvidence` (nav group, `aria-pressed`, labeled region, UI-E1 order, not-recorded labels, per-attempt routes, failures open). `test-model.mjs` UI-E1 test; browser test covers Enter/Space, Tab/Shift+Tab, polling retention without focus loss, cross-task isolation. |
| AC-3 | COVERED | `outcomeOnly` disables resume/approve/repair/recovery/cleanup for complete and pending-manual-acceptance; existing `readOnly`, `running`, `stageExhausted`, `needsDecision` conditions preserved; `TicketDecision` retained. Browser test asserts zero POSTs across complete/stale/pending/running/readonly/exhausted/unknown states. `test-browser.mjs` asserts `pending_manual_acceptance` is never `complete`. |
| AC-4 | COVERED | `intake.jsx`/`operations.jsx` unchanged; intake journeys retained in `test-intake-browser.mjs`; prior browser evidence under `docs/138/browser-evidence/intake*` and `operations*`. |
| AC-5 | COVERED (WARN: operator acceptance pending) | `npm test` 24/24 pass; `npm run build` exit 0 and reproduces committed `dist/assets/app.js`/`app.css` hashes exactly; 44px, focus, wrapping, contrast and overflow assertions in `test-intake-browser.mjs`; 1440/390 screenshots retained. |
| AC-6 | WARN — outside drift scope | Review, QA receipts and publication are controller-owned and pending; not a drift finding. Manual acceptance remains pending. |

---

### Summary
- BLOCK: 0
- WARN:  2 (AC-1/AC-5 operator visual acceptance pending; AC-6 downstream receipts pending)

### Verdict
APPROVE
