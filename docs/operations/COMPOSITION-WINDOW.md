# Retained composition wall window

## Behavior

PR #86 at `284d9c43b0af7feb5913dda23eb09dff001593df` accounts for active preparation time and fixes a composition deadline when authorization is issued. Its duplicate detection includes operator identity. After expiry, another identity could therefore obtain a later deadline for the same assessed graph.

The controller now caps every subsequent composition authorization at the earliest retained composition deadline for the task. An expired window rejects new authorization before ledger mutation or child dispatch. A narrower intermediate reservation remains effective even when a subsequent assessed graph permits a larger allowance. The retained authorization ledger supplies the original-window evidence; no second mutable authority record is introduced.

Idle time before the first composition authorization remains outside the active preparation profile. Exact request replay returns the original receipt, and execution still enforces its original deadline. This change does not authorize a continuation or reset an allowance.

Source: `scripts/nightshift-package-controller.py`, `Packages.authorize`.

## Validation

Independent review reproduced the two identity/expiry failures on the original PR #86 head. Four regression tests pass with the change in 13.705 seconds, covering identity changes, restart after expiry with no ledger mutation or dispatch, idle before first authorization, and changed bindings that narrow then expand their graph ceiling.

The existing nine wall-accounting tests pass in 23.388 seconds. Independent review also passed those nine tests and eight bundle tests. Controller SHA-256: `abddfcf4a660913fc4c519165fb9044c410d567bc0beb8060d05ae1fdf010209`.

Source: `tests/test-package-composition-window-review.py`, `tests/test-package-wall-review.py`, `tests/test-package-authoring-review.py`.

## Status

Implementation: independently reviewed synthetic regression fix. Integration: focused follow-up to PR #86; no merge performed. Certification: live endpoints, conflict-safe concurrency and nested composition remain unclaimed. No real provider, ticket restart, live allowance, installed runtime modification or deployment occurred. Provider token usage, KV-cache reuse and billing are unknown.

Actual Chromium 153.0.8010.12 and launcher acceptance passed on runtime revision `8431ed2bb1acc7291949bb6c076633cf28973d8a`: 14 synthetic calls, zero replay calls, 30,599 recorded packet bytes, 4.953324001995497 worker seconds and 4.814988851547241 active preparation seconds. Unknown calls, unknown preparation phases and remaining execution reservations were zero. Exact individual argv sizes are retained separately in `COMPOSITION-WINDOW-VALIDATION.json`; no provider token/cache/billing measurements are available. The fixture authored inline child artifacts without creating child files in the caller checkout.
