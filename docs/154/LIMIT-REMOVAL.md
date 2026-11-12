# Operator-directed limit removal

The operator requested removal of arbitrary automatic limits after optional adapter healing prevented the requested factory run from starting.

## Behavior

- Optional adapter reconciliation retains cumulative failure evidence. A failed reconciliation does not block a requested source-checkout run or overwrite unrelated installation links.
- New ticket accounting and behavioral proof have no default work-time, call-count, or repair-count ceiling. Counters, pending reservations and receipt validation remain active.
- Automatic repairs continue without a fixed attempt count. Explicit operator limits remain enforceable. Unchanged failed inputs, missing authorization, cancellation and unresolved external dependencies remain concrete blockers.
- Explicit positive operation and recovery allowances are accepted without a fixed numeric upper ceiling.
- Existing ticket ledgers with ambiguous numeric limits remain unchanged: their records do not establish whether those limits were defaults or explicit operator choices. Legacy retry defaults with known fixed-code provenance are reconciled with prior limits and counters retained.

## Verification

Focused regression suites exercise execution beyond former limits, explicit bounded allowances, cumulative receipts, cancellation, reviewer independence, and unlimited-budget display. These are local candidate checks, not installed/live certification of issue 154.

Sources: `scripts/nightshift-update.py`, `scripts/nightshift-ticket-budget.py`, `scripts/nightshift-retry-budget.py`, `scripts/nightshift-behavior-proof.py`, `scripts/nightshift-controller.sh`, `scripts/nightshift-controller-recovery.py`, `scripts/nightshift-operations.py`, `dashboard/src/model.mjs`.
