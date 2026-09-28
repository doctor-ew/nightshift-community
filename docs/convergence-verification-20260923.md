# Bounded repair convergence verification

## Local implementation

The isolated branch `nightshift/bounded-convergence` starts at published revision
`6272568`. The original dirty checkout and installed launcher were preserved.

Registered source-review repairs now persist canonical artifact-content signatures
against review reservations. An identical signature previously finalized as
`substantive` is refused before another reservation or provider invocation. JSON
formatting, key order, finding IDs and output names do not count as repairs.
A changed artifact may be admitted under the original budget. Pending and
infrastructure failures retain separate handling. No retry allowance increased.

The dashboard reads `repair-admission.json` through its existing gate reader and
shows `needs-decision` with the retained cause and unblock path. Later admission
changes this guard to `skipped`; it never approves the source or behavioral gate.

Coverage is limited to registered artifacts reviewed through the bounded source
dispatcher. Different artifact content may still contain the same semantic defect.
Automatic repair-provider switching and historical-signature backfill are not
implemented. No token, Jev, RTK or billing savings are claimed.

## Verification

- Repair dispatch: 2 integration tests passed. The new test failed before the fix.
  It uses stub provider reports and a fresh CLI process to prove recurrence refusal,
  unchanged budget bytes, portal visibility, changed-content admission, pending
  rejection and continued infrastructure retry handling.
- Deterministic repair checks: 19 tests passed.
- Persistent ticket budgets: 9 tests passed.
- Retry accounting, admission and audited continuation: shell suite passed.
- Dispatcher: 128 assertions passed.
- Dashboard: 10 tests passed.
- Whitespace check passed.

## Actual deterministic consumer execution

`tests/prove-repair-convergence.py` executed a synthetic consumer with an incorrect
multiplier. Its behavior check failed; the real repair checker confirmed failure;
one deterministic apply corrected the pinned value; three consumer assertions
then passed. The original snapshot remained unchanged. This was actual Python
execution, not a mocked provider or static approval.

Elapsed: 0.162 seconds. Limit: 30 seconds and zero provider launches.
Repairs: 1. Behavior retries after repair: 1. Provider tokens: 0.
Assistant-session tokens and historical subscription usage: unknown.

Reproduce with a fresh output path using:

```sh
python3 tests/prove-repair-convergence.py --out <new-evidence-directory>
```

Retained results are in `convergence-proof-20260923/consumer-*.json`.
This is a synthetic deterministic workflow, not full factory certification.

## Bounded live-provider attempt

The configured Codex route selected `gpt-5.4`; subscription authentication was
confirmed. One instrumented provider launch was reserved. The dispatcher returned
`model_unavailable`; no behavior verdict was produced. Elapsed: 3.903 seconds;
accounted active time: 3.389 seconds. Limits: one launch and 90 aggregate active
seconds, with a 110-second outer timeout. Provider retries: zero. Tokens and
provider-internal calls: unknown. The ledger was not expanded or reset.

An earlier invalid receipt flag was rejected before provider admission. Its
failure is retained separately as `preflight-live-*`; it consumed no provider
reservation. Claude's selected profile had no subscription login after API
credentials were removed; no Claude model call was made.

See `convergence-proof-20260923/live-result.json`, `live-budget.json`,
`live-metrics.json` and `live-timing.json`. The local portal at
http://127.0.0.1:57293 serves both synthetic completion and live-provider failure.
HTTP identity, HTML and state were checked; visual browser rendering was not.

## MEX verification checklist

- Pass: installed naming and runtime-neutral roles are preserved.
- Pass: upstream tickets and local beads identity are unchanged.
- Pass: fixtures cover the changed admission boundary.
- Not applicable: trajectory evidence schema was not changed.
- Partial: scaffold statements cite source files; graph grounding could not run
  because this isolated checkout has no graph index.
- Pass: live readiness and unknown accounting are explicitly limited above.

MEX context used: `.mex/AGENTS.md`, `.mex/ROUTER.md`,
`.mex/context/architecture.md`, `.mex/context/conventions.md`,
`.mex/context/proof-accounting.md`, `.mex/patterns/debug-proof-budget.md`.
Scaffold and decision-log changes are local working-tree artifacts until committed
and pushed. This work does not certify, rebuild or resume the separate coach.
