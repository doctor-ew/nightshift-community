# Efficiency roadmap

This document tracks what #8 (preflight admission + run measurements, this ticket)
actually delivered, and how the follow-on efficiency tickets build on it. See
`docs/HARDENING-ROADMAP.md` for the broader prioritized hardening sequence this sits
inside of, and `docs/RUN-MEASUREMENTS.md` for the full behavioral description of what
follows. Nothing in this document asserts a follow-on ticket is done — every item
below other than #8 itself is explicitly open.

## What #8 delivers

- A deterministic, read-only preflight admission gate
  (`scripts/nightshift-preflight-check.sh`) that runs baseline, ticket-identity,
  manifest, and worktree-collision checks — in that order — before
  `nightshift-factory.sh` invokes any provider. This avoids paying for a provider
  invocation that was always going to fail on an avoidable, statically-checkable
  problem.
- A shared, typed run-metrics writer (`scripts/nightshift-run-metrics.py`) that
  establishes one measured baseline per run: elapsed time, terminal status, observed
  dispatcher stage/provider/model/duration/status, run-local repair counts, and
  actually-reported token usage (never estimated, never guessed).
- The baseline predicate factored out of `nightshift-factory.sh`
  (`scripts/nightshift-baseline-check.sh`) and a read-only `check` operation added to
  `scripts/nightshift-worktree.sh`, so downstream tickets that need the same
  predicates (a status dashboard, a batch pre-flight summary, a smarter retry policy)
  can call them directly instead of re-deriving the logic.

This is the "establish baseline" ticket referenced by the hardening roadmap; the
tickets below are the measured, targeted work that baseline makes possible. None of
them are scoped or implemented by #8.

## Follow-ons this baseline unblocks

- [#9 Bounded handoffs](https://github.com/doctor-ew/nightshift-community/issues/9) —
  needs a stable, typed run/observation record to hand context through; #8's
  `summary.json` and observation events are that record, not a new one #9 has to
  invent.
- [#10 Evidence cache](https://github.com/doctor-ew/nightshift-community/issues/10) —
  reuse-verified-work caching needs provenance and invalidation signals; #8's
  run/observation identifiers give it something concrete to key off of, but the cache
  itself, its invalidation rules, and its trust boundary are unimplemented here.
- [#11 Targeted repairs](https://github.com/doctor-ew/nightshift-community/issues/11)
  — needs to distinguish a substantive repair from an infrastructure retry; #8's
  `nightshift-retry-increment.sh` repair-delta events are that distinction, but #11's
  actual "avoid repeating unaffected work" logic is not built here, and #8 does not
  touch the existing adversarial repair budget policy (that stays owned by #20).
- [#12 Measured gearshifting](https://github.com/doctor-ew/nightshift-community/issues/12)
  — matching model capability to job needs a real measured baseline (duration, usage,
  outcome) per gear/role/provider first; #8's observations are that baseline. #12
  itself — the actual gear-selection policy change — is not implemented here.
- [#13 Pre-build behavioral proof](https://github.com/doctor-ew/nightshift-community/issues/13)
  — independent of #8; can and should proceed in parallel per the hardening roadmap.
- [#14 Optional MEX spike](https://github.com/doctor-ew/nightshift-community/issues/14)
  — depends on #9's handoff contract, not directly on #8.
- [#18 Provider-neutral core](https://github.com/doctor-ew/nightshift-community/issues/18)
  — #8's new scripts follow the existing provider-neutral convention (routing/prompt/
  input as data, no provider-specific tool names in shared logic) but do not
  themselves complete #18's broader adapter-boundary work.
- [#19 Regression guard](https://github.com/doctor-ew/nightshift-community/issues/19)
  — #8's own regression fixtures for the new scripts are owned by the pipeline's test
  stage, not authored by this implementation pass; #8 does not build #19's general
  scoped-scan guard either way.
- [#20](https://github.com/doctor-ew/nightshift-community/issues/20) — owns the
  adversarial repair budget policy. #8 explicitly does not alter that policy; the
  retry-delta metrics it adds are additive observation only.

## Non-goals of this ticket

- No caching, no handoff-context compression, no gear-selection policy change, no
  MEX integration. Those are #9–#14.
- No change to the adversarial repair budget (#20 owns it) — #8 only observes and
  records deltas after a repair counter is already, separately, incremented.
- No cost/billing estimation from token counts. Usage is reported as raw
  `input_tokens`/`output_tokens` when a provider's own envelope exposes them; #8 does
  not convert that into a dollar estimate anywhere.
