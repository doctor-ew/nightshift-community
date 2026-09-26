# Recorded recovery progress

The console shows retained recovery steps even when the original pipeline remains
blocked before adoption. Verification, adoption, review, drift and QA statuses are
recorded observations. A `running` session is not a process heartbeat: after a
crash the same record can remain. The console labels this state as recorded
recovery and keeps the separate worker snapshot explicit.

The overlay does not change ticket state, infer worker liveness, restart work,
renew allowances or suppress original failures. Changed evidence takes precedence
over recovery progress. Manual acceptance remains distinct from completion;
completion requires the existing validated controller outcome.

Validation uses two Python projection tests, 19 dashboard model tests and the
built-dashboard Chromium fixture `dashboard/test-recovery-progress-browser.mjs`.
The browser fixture covers recorded running and unchanged crash records, blocked
responses, manual acceptance, complete and stale states, literal untrusted text,
retained historical failure and narrow mobile layout. Its intercepted synthetic
requests are GET-only; no provider or controller mutation is invoked. Independent
code review approved the implementation.
