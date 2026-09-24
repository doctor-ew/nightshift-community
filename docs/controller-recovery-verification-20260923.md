# Recovery controller verification

## Implemented boundary

`scripts/nightshift-recovery-state.py` owns console repair progress for each ticket.
The existing ticket lock protects mutations. The record contains resolved policy
and routes, recorded operator answers, completed steps with evidence hashes,
unresolved findings, the next permitted action, a deadline, and append-only attempt
history. Existing provider-call and historical repair ledgers remain authoritative
for their respective accounting; this controller does not rewrite them.

Admission resolves the configured author, independent reviewer, and test reviewer
before starting a worker or charging a console repair attempt. Claude-only policy
selects fresh Claude review sessions through the existing dispatcher. Missing
routing fails admission without a model call or another configuration question.

Ordinary resume continues the first unfinished repair step. Successful proposal
and review receipts are reused only when their retained bytes, source corpus,
settings, operator decisions, routing, and role assets match. Changed inputs retain
previous results in history and invalidate reuse. Stage attempts remain capped at
three across invalidations and restarts. The recovery deadline is at most 600
seconds and cannot extend an existing ticket deadline. Pipeline continuation uses
the same remaining deadline.

An applied patch survives failed verification. A subsequent resume reuses the
proposal and review and continues verification. Worktree admission permits source
changes only when the complete input fingerprint still matches successful retained
verification evidence. This does not approve other delivery gates.

A zero process exit and a SUCCESS response without positive passing-test evidence
cannot pass repair verification. After pipeline continuation, the deterministic
final behavior gate is evaluated. Required manual acceptance is recorded as
pending, and ordinary resume does not launch another worker to reconsider it.
Other missing checks remain pending. The recovery controller never declares the
whole ticket complete from a provider or factory exit.

## Acceptance sequence

Run `python3 tests/test-console-repair.py`. The regression
`test_failure_sequence_reuses_answers_review_and_budget_then_reports_manual_pending`
reproduces the reported failure categories using retained synthetic ticket state:

1. Create an existing draft, sealed behavior evidence, a saved Claude-only answer,
   and a historical failed provider reservation.
2. Point routing at a missing file. Console repair rejects admission; no process or
   console repair-budget record is created.
3. Restore configured routing. Dispatch a proposal and a separate Claude review,
   then apply the targeted patch.
4. Return process exit zero and SUCCESS with zero passing checks. Verification
   rejects that response and retains the applied patch and unresolved finding.
5. Resume. Only verification runs; diagnosis and review are reused. An actual
   Python assertion checks the repaired source. The existing final gate evaluates
   sealed automated evidence and reports manual acceptance pending.
6. Repeat the answered question and request resume. The saved answer is returned,
   no new question is created, and no worker is launched for pending manual work.
7. Assert that the recovery deadline and historical ticket-budget bytes remain
   unchanged. Retained child-worktree repair and active-child rejection are also
   exercised.

`scripts/nightshift-agent.sh` is replaced only at the provider transport boundary
in this regression. The patch, Git checks, retained controller state, decisions,
source assertions, and final behavior gate execute locally. This is offline
controller acceptance, not a replay of private consumer artifacts or live model
certification. No consumer ticket was restarted and no historical allowance was
expanded.

## Validation

- Console repair: 12 tests passed.
- Recovery checkpoints: restart reuse, changed-input invalidation, tampered
  evidence rejection, deadline exhaustion, and persistent stage caps passed.
- Console actions, retained-worktree cleanup, and manual acceptance passed.
- Operator decisions: 11 tests passed.
- Persistent ticket budgets: 14 tests passed.
- Routing resolution: 4 tests passed.
- Dispatcher: 130 assertions passed, including fresh Claude review provenance.
- Review reuse: 5 tests; writer briefs: 2 tests; repair dispatch: 2 tests; retry
  accounting and audited continuation passed.
- Repair leases: 10 tests; release inputs: 9 tests passed.

## Remaining scope

This is a structural repair of console recovery, not migration of every factory
stage into a single deterministic ticket state machine. Factory stage selection
still has instruction-driven paths. Legacy prose-only results are not silently
imported as successful checkpoints. Completion of the full ten-minute live spec
workflow remains unproven; issue 49 stays open.

The code graph was refreshed and used for affected-source inspection. Automatic
worker graph retrieval, CxFlow validation, and measured Jev benefit remain separate
work. No Jev savings or new live-provider performance result is claimed.

MEX context used: `.mex/AGENTS.md`, `.mex/ROUTER.md`,
`.mex/context/architecture.md`, `.mex/context/conventions.md`,
`.mex/context/proof-accounting.md`, `.mex/patterns/debug-proof-budget.md`.

MEX verification checklist:

- Pass: installed names retain the prefix and shared roles remain runtime-neutral.
- Pass: upstream ticket authority and local ledger identities remain separate.
- Pass: existing and new fixtures cover the changed controller boundary.
- Not applicable: the trajectory evidence schema was not changed.
- Pass: implementation claims cite source files; graph refresh includes the new
  recovery module. Dynamic Python module loads are not complete graph call edges.
- Pass: live readiness and remaining factory migration are explicitly limited.
