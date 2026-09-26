# Operation cancellation and reconciliation

## Cancellation authority

The shared `cancel` action names a retained grant, its cancellation binding, the
original operator identity and an idempotency request. The binding covers the
project, task, grant and immutable authorization request digest. Operator equality
is an audit check within the authenticated local API; it is not shared-service
identity or authorization for a remote tenant.

Cancellation writes a separate durable intent under its own lock. It does not
wait for the operation execution lease or signal the browser server. A requested
cancellation is distinct from confirmed process termination. The owned runner
checks cancellation before spawning and while running. Its supervisor terminates
and reaps its owned command group; unrelated processes are never selected by a
name or a retained PID. Ownership receipts record local lifecycle observations.
Receipt-write failures still run cleanup.

A cancelled grant stays cancelled across restart and duplicate requests. The
executor checks before reservation, dispatch and integration. Integration holds
all applicable cancellation locks, so an acknowledged cancellation cannot race a
subsequent product write. No rollback of operator edits or partial files occurs.

## Package composition

`packages-cancel` uses the same intent contract for a composition grant. Children
receive inherited cancellation restrictions and narrowed deadlines in their first
durable authorization write. Reusing a child authority retains every previous
parent restriction. The child runner checks its own and all parent cancellation
paths. Parent composition checks before later child dispatch and before recording
integration acceptance. A completed child is retained even when the parent stops.

## Unknown usage

An invocation without a controller completion receipt keeps its reservation as
unknown. Measured local shutdown time is not substituted for provider execution or
billing. A known cancellation before spawn may record zero execution; an already
started invocation does not. Completed worker receipts settle their measured
duration once. Cancellation does not replenish calls, deadlines or budgets.

Verification retains partial per-check output and its hash outside the disposable
source copy. Worker output, completion, ownership and checkpoint evidence are
included in reconciliation assessments. Local receipt accounting does not provide
remote exactly-once execution or billing guarantees.

## Reconciliation

The shared `reconcile` action names the original operation request, exact current
reconciliation binding, original operator and a resolution:

- `finalize` validates a retained worker completion or checkpoint and reuses the
  existing recovery/finalization path. It does not dispatch a provider. A semantic
  operation without a complete retained checkpoint remains blocked because its
  missing semantic judgments cannot be recreated by reconciliation.
- `preserve` requires cancellation, leaves partial files and evidence intact, and
  records `cancelled_unknown`. Unknown call reservations remain charged. Any later
  work requires separately eligible, explicit authority; this action grants none.

Changed source, configuration, checkpoint bytes, evidence or controller policy
blocks finalization. Duplicate reconciliation reuses the receipt; a stale formerly
passed result cannot be reported as current. The browser and CLI use these same
controller actions. The UI distinguishes cancellation requests, unknown execution,
retained completion and explicit preservation.

## Verification boundary

Independent fixtures cover cancellation before dispatch, restart, wrong operator,
stale authority, completed-worker recovery, partial checkpoints, unknown usage,
semantic reconciliation without evaluator dispatch and receipt-persistence failure.
Actual process fixtures include a TERM-resistant owned child and an unrelated
process. Parent fixtures cover active-child cancellation, between-child stopping,
pre-acceptance cancellation, additive restrictions and a crash immediately after
child authority is saved.

All provider execution is synthetic and all repositories are disposable. No real
provider, retained live ticket, installed runtime, live allowance, merge or
deployment is changed. Integration and live certification are separate statuses.

Exact browser/controller revision: `5e6747f9b8877601bc83a4d38cf20e4cb0c829c3`.
The full operation suite passed 149 tests at the preceding cancellation runtime
`bda1654739d981c3cb65cc7659f9fee503ddccd1`; intake integration passed 41. After
integrating clarification retention, nine additional decision tests, eleven
reconciliation tests and thirteen question tests passed. A transport fixture was
adapted to provide the now-required retained grant.

The final Chromium 153.0.8010.12 run dispatched one synthetic request: 3,872
launcher argument bytes and 650 operation packet bytes, with zero replay calls.
Its interrupted execution retains one unknown call and the full 30-second
reservation. Zero measured seconds means no completion receipt was obtained; it
is not a zero-use claim. Provider token usage, cache usage and billing are unknown.
Exact structured evidence: `CANCELLATION-RECONCILIATION-VALIDATION.json`.

This slice integrates #93 namespace binding, #94 semantic provenance and #97
clarification retention above #95. It has not been merged into the default branch
or installed. #96 typed verification integration remains a subsequent slice.

## Compatible base and startup follow-up

The replacement branch starts at the actual #95 head
`6fef11f8c37f8a4b2b19b3ece41d0fa5d0c1d894`. It preserves the reviewed #98
tree and integrates #100's owned-process startup fix. It does not rewrite or
remove #98 history. Runtime `6a306702dc4f4f25f1cd2caaaac542e9a95b5796`
passes nine startup, eleven reconciliation and six parent cancellation tests.
The actual Chromium cancellation flow passes with one synthetic call, zero replay
calls and the same unknown-call reservation. The original #98 branch conflicts
with its base and is superseded for integration by this replacement.
