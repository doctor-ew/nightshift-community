# Bounded continuation

New instrumented tickets receive a persisted 600-second wall-clock deadline from
first reservation. Waiting and restarts do not reset it. Existing ledgers retain
their original accounting; they are not retroactively rewritten to imply coverage.
Factory and role dispatchers check the shared deadline and stop provider processes
when it expires. Enforcement polls approximately every two seconds; process cleanup
adds a short grace period. This is a deadline, not a promise of successful delivery.
New-ticket setup before first reservation is outside this deadline.

An operator can explicitly grant a continuation using
`scripts/nightshift-continue.sh jira:TICKET` from the application checkout. The
helper grants at most 600 more aggregate active seconds and sets a new wall-clock
deadline immediately, including subsequent factory preflight time. It preserves
all reservations, prior limits in an audit entry, usage and the original call cap.
It refuses unfinished reservations, an exhausted call cap, or more than 600 seconds.
It does not itself launch a model. Ordinary resume cannot renew the allowance.

The locally installed `nightshift-test continue jira:IF-325` wrapper validates
Claude subscription authentication, grants that window, then invokes the patched
factory with Claude-only routing. Existing artifacts are reused; no review or test
result is promoted to pass by continuation. The wrapper does not execute a model
when invoked with `--help`. The local install remains separate from publication.

The portal reads budget accounting without writing it. Its ticket card displays
aggregate active seconds remaining, reserved instrumented launches, and wall-clock
seconds remaining when a deadline exists. Provider-internal calls, tokens, billing,
and historical activity outside instrumentation remain separately unknown.

## Verification

- 13 budget tests passed, including persistence through idle/restart, explicit
  continuation audit, unchanged call cap, rejection of unfinished work, and read-only
  snapshots.
- Factory CLI regression passed using local provider stubs. A stub that ignores
  SIGTERM was terminated at the short test deadline; unchanged restart was denied.
- Console action regression passed with process inspection enabled.
- 10 dashboard model tests passed and the production bundle rebuilt.
- The live local portal serves the budget card. IF-325 was stopped, with 14 recorded
  reservations and 3597.389 aggregate active seconds used; 2.611 seconds remained
  in its original allowance. No continuation was granted during verification.
- External model launches and retries for verification: zero. Model tokens: zero;
  assistant-session usage is outside harness accounting. Full ticket delivery within
  ten minutes has not been demonstrated. No publication or successful gates claimed.
