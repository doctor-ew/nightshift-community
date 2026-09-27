# Hardening after the first completed Jev-mode recovery

Follow-ups from #128, all verified against the completed run.

- **Binding independent of environment-only route config.** After authorization,
  `current_binding` (used by `validate_adopted` and acceptance) takes the reviewer
  route and allowance from the recorded session evidence when, and only when, the
  plan digest is unchanged. Workspace, runtime assets, checks, spec, findings and
  plan still must match. A dashboard or validator started without
  `NIGHTSHIFT_JEV_*` no longer reports accepted evidence as stale.
- **Jev-engine cross-session reuse.** The Jev engine adopts a completed yes/no for
  the byte-identical packet from an earlier authorized session under the same rules
  as the independent engine (policy, settings and rubric in the key; origin
  re-validated with its raw Jev answer and escalation review; abstentions never
  reused; no chaining). Settled answers stay settled even though Jev scores vary
  slightly between calls.
- **Run estimate counts reuse.** `run_estimate.provider_calls.reusable_answers`;
  expected and maximum calls and tokens cover only fresh questions.
- **Readable finding claims.** Structured retained findings are stated as "the
  retained failure '<problem>' (category: <c>) recorded in <file>" instead of raw
  JSON (a raw record scored 0.31 in the live run).
- **CI speed.** `nightshift-checkout-identity.py` caches the repeated
  `git rev-parse --show-toplevel --git-common-dir` per process (scripts are loaded
  afresh per call, so the cache lives in `sys.modules`). An entry is reused only
  while the checkout is provably the same (device/inode of `.git` and the common
  dir, and worktree pointer content). On a representative operations test:
  1,570 → 542 subprocess spawns, 22.9 s → 15.8 s. The full-corpus workspace hash is
  deliberately not cached.

Validation: `tests/test-deterministic-evidence.py` (binding without route
environment; Jev reuse after an interrupted session; estimate reuse),
`tests/test-reviewer-reuse.py` (finding text), `tests/test-checkout-identity.py`
(a different checkout at the same path is not served from cache).
