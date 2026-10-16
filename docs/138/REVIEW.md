## Code Review (nightshift-review)

**Task:** 138
**Date:** 2026-10-15
**Mode:** post-impl
**Scope:** 9 files outside `docs/138` (vs 758ba3d, the branch base; `main` is not the merge base for this branch)
**Reviewer:** nightshift-review harness (review attempt 2)

TDD integrity: PASS. Spec source for lenses: `docs/138/SPEC-DIGEST.md`.

Attempt 1 returned REQUEST CHANGES with one BLOCK (read-only browser regression). That review is retained at `docs/138/review-1-evidence/REVIEW.review-1.md`. Implement attempt 2 repaired it; this attempt re-reviews the current candidate.

---

### DRY
| Severity | Confidence | Finding | Location |
|----------|-----------|---------|----------|
| WARN | HIGH | The completed/pending-acceptance predicate is written again as `outcomeOnly`; `continuationControl` already holds the same predicate. | dashboard/src/app.jsx:197, dashboard/src/model.mjs:147 |

### SOLID
| Severity | Confidence | Principle | Finding | Location |
|----------|-----------|-----------|---------|----------|
No findings.

### ACID
| Severity | Confidence | Property | Finding | Location |
|----------|-----------|----------|---------|----------|
No findings. Selection is local component state keyed by task; polling does not reset it.

### CoC
| Severity | Confidence | Finding | Location |
|----------|-----------|---------|----------|
| NOTE | LOW | The "Open tracker" link and the Spec/QA/Deploy stage labels from the removed timeline are no longer rendered; stage buttons show raw stage ids. | dashboard/src/app.jsx:117-130 |

Attempt 1 BLOCK (`dashboard/src/app.jsx:228-237`) is resolved. The "Recorded allowance and continuation" disclosure renders `open`, so "Grant 10 minutes & continue" is accessible by role. Read-only disabling and the `continue` request body are unchanged. `tests/test-console-read-only-browser.py` now passes.

### Big O
| Severity | Confidence | Complexity | Finding | Location |
|----------|-----------|-----------|---------|----------|
| NOTE | LOW | O(rows) | `stageEvidence` re-filters rows and rebuilds the timeline on every render. Bounded by per-task rows. | dashboard/src/model.mjs:3-25 |

### LLM Trust Boundary
| Severity | Confidence | Vector | Finding | Location |
|----------|-----------|--------|---------|----------|
No findings. Receipt text and reasons render as React text nodes, with no HTML injection or dispatch path from inspection.

---

### Summary
- BLOCK: 0 (HIGH: 0, MEDIUM: 0)
- WARN:  1
- NOTE:  2

### Verification
Logs are under `docs/138/review-2-evidence/`.
- `bash scripts/nightshift-tdd-integrity-check.sh 138`: PASS. `git diff --check`: clean.
- `node --test test-model.mjs` (dashboard): 24 pass, 0 fail.
- `node build.mjs` (dashboard): exit 0; `dist/assets/app.js` and `app.css` hashes unchanged after rebuild (reproducible).
- `tests/test-console-read-only-browser.py`: PASS (previously failing).
- `tests/test-operation-browser.py`, `tests/test-intake-browser.py`, `tests/test-delivery-browser.py`, `tests/test-operation-cancellation-browser.py`, `tests/test-package-authoring-browser.py`, `tests/test-dashboard.sh`, `dashboard/test_server.py`: pass.
- `tests/test-recovery-independent.sh` (4 failures, 3 errors) and `tests/test-semantic-transport-review.py` (1 failure): same failing test names as at 758ba3d (`docs/138/review-1-evidence/baseline-*.log`); unrelated to this change.
- Manual acceptance C-6 remains pending; Drift and QA remain controller-owned.

### Trend (vs last run)
- CoC: BLOCK 0 (-1)  WARN 0 (—)  NOTE 1 (—)
- DRY: BLOCK 0 (—)  WARN 1 (—)  NOTE 0 (—)
- SOLID, ACID, Big O (NOTE 1, —), LLM Trust Boundary: unchanged.

### Verdict
APPROVE
