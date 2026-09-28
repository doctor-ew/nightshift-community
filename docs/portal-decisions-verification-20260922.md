# Portal decisions and repair evidence verification

The portal previously sent parent workflow logs while omitting relevant child public scenarios. The repair bundle now follows registered child worktrees and projects public JSON without held-out subtrees. Repairs own the child lock through verification.

Operator questions support up to three choices and a free-text answer. Answers are version-bound, retained, and queue continuation with the chosen repair provider; active workers are allowed to exit first. Failures retain the answer and expose retry. Answers never manufacture gate results.

Validation on 2026-09-22:
- 12 repair tests, 10 decision tests, 10 lease tests passed.
- 11 dashboard HTTP tests, 3 dashboard-start tests, 10 dashboard model tests passed. Console-actions and cleanup integration suites passed.
- Browser validation in an explicitly synthetic Git fixture submitted both a selected option with detail and a free-text-only answer. Both persisted. Missing fixture worktree correctly produced a visible retryable continuation failure; this is not evidence of a live build completing.
- Live read-only repair bundle included c05/c06 public cases and calibration fixtures in a bounded 99,969-character bundle. Private files were not read.
- Independent review resolved evidence omission, concurrent child repair, provider preservation, and stale canonical PID reuse findings; final lease correction passed review.

Build status is independent: this change does not approve the Jobs Night specification or behavioral gates.
