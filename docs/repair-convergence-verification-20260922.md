# Repair convergence and spending controls

Implemented in canonical Nightshift, 2026-09-22.

- Exact JSON repair contracts retain a hash-pinned original. Check requires original-fails/current-passes. Explicit apply repairs one unchanged artifact atomically without a model call; snapshots remain intact. Receipts never approve review or behavioral gates.
- Source-review dispatch executes registered repair checks before reserving a retry or launching a provider. Check errors cannot reuse an old passed receipt.
- Resolved single-ticket factories propagate one persistent common-Git allowance to role dispatchers. Defaults: 64 process launches, 3600 aggregate active seconds. Limits are pinned; restart or changed environment cannot expand them. Active factories/providers are interrupted on time exhaustion, with bounded TERM/KILL handling.
- Factory and author instructions require narrowed evidence, stable findings, mechanical metadata corrections, and a changed repair provider for recurring findings within provider policy. Provider replacement is an orchestrator instruction, not an automatic router implementation.

Validation: 19 repair-check tests, 1 real-checker dispatcher admission integration test, 9 budget tests, 128 dispatcher assertions, retry-budget suite, factory CLI suite (including TERM-ignoring mock and exhausted restart refusal), shell syntax and whitespace checks passed. Provider stubs were used in launcher tests; no live proof success is claimed.

Consumer evidence: Jobs Night c06 turn 3 now explicitly requires exactly one revised pending sentence before turn 4 accepts “that sentence.” Deterministic apply and canonical scenario validation passed. Original failure snapshot and failed reviews remain retained. No independent approval or full coach completion is claimed; SPEC digest bindings and independent review must be refreshed before any proof seal.

Coverage limits: budgets measure instrumented process launches/aggregate active time, not provider-internal API calls, tokens or subscription billing. Historical usage remains unknown. Batch orchestration and direct proof calls retain separate accounting. Repair admission only enforces registered manifests, and exact-field checks prove the structural correction, not runtime model behavior. Unfinalized interrupted reservations remain charged conservatively.
