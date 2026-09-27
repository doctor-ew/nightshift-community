# Semantic evaluator implementation identity

## Defect and correction

At PR #88 revision `725af62ad85ac84918eec0b811605c1515c1285e`, changing evaluator/mapper implementation invalidated the operation result but could still reuse three semantic approvals from the old implementation. The semantic authority omitted the implementation identity.

The authority now includes SHA-256 identities for `nightshift-operation-decisions.py`, `nightshift-decision-engine.py`, `nightshift-recovery-decisions.py` and `nightshift-efficiency.py`. Receipts retain that identity. Validation recomputes both the current asset set and the complete authority from the task, worktree, reviewer policy, route and operation. Relabeling an old receipt with new asset metadata cannot preserve its old authority.

Unchanged implementations reuse current receipts. Changed implementations require new reservations within the original allowance. Missing assets or legacy receipts without identity fail closed; no allowance is renewed. Provider configuration remains explicit and unchanged.

## Validation

Six independent tests pass in 22.353 seconds. Each changed asset invalidates old receipts and reserves three evaluator calls plus three independent escalation calls. Unchanged assets reuse three receipts with zero calls. Missing identity/assets, metadata relabeling and exhausted retained budgets cannot pass or manufacture authority.

Ten existing handoff tests pass in 29.462 seconds and three version 1 operation-decision tests pass in 24.544 seconds. Eleven existing semantic regression tests passed before the final authority self-consistency check. Final bridge SHA-256: `c89e228baf576cde7ec2cbc5e4984245318151e9c33bfeb38f79f43749734426`.

## Status and limits

Implementation: independently reviewed cache-identity correction on #88. Integration: remaining semantic role-provenance and explicit escalation-coverage findings are not fixed by this change. Configured-disabled semantics and stage opt-in behavior also remain part of #68 acceptance. Certification: synthetic only; no accuracy, calibration or savings claim. Tokens, provider KV-cache consumption, billing and independent reviewer usage remain unknown. No live provider, runtime activation, merge or deployment occurred.

Committed-revision receipt at `92d9559ad33aa19db9568cb31ae378b404f090ee`: 8 synthetic calls (3 evaluator, 3 escalation and 2 preparation workers), 3 semantic receipt-cache hits and 0 replay calls, 24,597 request bytes, 0.0037029160048405174 measured synthetic worker seconds, 0 unknown usage. The fixture passed in 3.513 seconds. Exact sizes are in `SEMANTIC-CACHE-VALIDATION.json`; these stub timings are not evaluator latency or quality measurements.
