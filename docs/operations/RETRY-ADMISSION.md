# Retry admission before supervised execution

## Defect and correction

The bounded supervisor previously accounted only failed operations, after worker
execution. A retained exhausted retry ledger therefore allowed another worker,
and successful operations did not consume the ledger's total invocation ceiling.

`Operations.execute` now reserves the existing retry ledger for supervised work
after authority and preflight validation, before recording or dispatching a new
operation. `nightshift-retry-budget.py` performs an exclusive pending-request
check within its existing locked transaction. Its default legacy behavior remains
unchanged. The authorization binds the retry implementation hash.

The supervisor finalizes successful and failed reservations idempotently. Replayed
results and checkpoint recovery reuse the existing request. An unresolved different
request or an exhausted ledger blocks before any provider reservation or execution.
A crash between retry reservation and operation recording can resume the same
supervisor-owned request; another request cannot consume that pending reservation.
Rejected stale or expired authority creates no orphan retry reservation.

## Independent evidence

Six independently authored synthetic regressions in
`tests/test-operation-supervisor-admission-review.py` pass in 20.423 seconds.
They cover retained exhaustion, another pending request, successful accounting,
replay, stale and expired authority, and a crash after provider completion before
supervisor acknowledgement. The existing stopped-ledger regression now requires
zero worker calls. The legacy retry-budget suite also passes.

Independent code review approved these SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| `scripts/nightshift-operation-supervisor.py` | `bc79604a5d9e5d94155fe41ad0a8b86d6ab78942d945593070359259355ce1e1` |
| `scripts/nightshift-operations.py` | `f0f033997cd5b97595c75fdd8893941136d9508792bcf310bdeb3fdcbe6f9a36` |
| `scripts/nightshift-retry-budget.py` | `4fa28f5c7606ae0608901dd6d60d53eed59e76641a51062adb6cc81b4d29e2c9` |

## Integration and certification

This focused follow-up depends on PR #78 at
`143319d6d88f4ad6eb517b37e2ceeff11aaaf242`. PR #79 remains retained comparison
and synthetic evidence, not a second scheduler to integrate. No existing operator
runtime, real ticket, live allowance or provider was changed. No merge or deployment
occurred. #11 remains open for broader endpoint and live acceptance.
