# Reviewer answer reuse and timing-normalized observations

A live recovery run stopped on one correct abstention after 30 reviewer answers.
Every later session would have paid for all of them again, for two reasons:
test output carries timings that differ on every run, so no packet was ever
byte-identical; and answers were cached only inside the session that paid for them.

## Timing-normalized observations

Observation evidence is a deterministic view of the verified raw check output
(`observation_view`, `timing-normalized-v1` in `scripts/nightshift-recovery-decisions.py`).
It replaces only duration tokens, line for line: the final `(0.73ms)`-style
measurement on spec-reporter result lines (`✔ ✖ ✓ ✗`; TAP lines are never
edited), node's
`duration_ms` summary and TAP fields, unittest `Ran N tests in X s`, pytest
`in X s` summaries, and JSON `elapsed_*`/`duration_*` fields with a unit suffix.
Asserted values stay visible: a plain line ending in `(200ms)`, a bare `duration`
key, and a title ending in `(5s)` before the runner's appended measurement are
all kept. Known limit: a result line whose title ends in `(N unit)` from a
reporter that appends no measurement would lose that token; node:test and mocha
always append one. Nothing else
changes, and line counts are preserved so evidence spans stay exact. The raw output
and its hash remain in `verify.json`; the raw hash is still checked before the view
is taken. On a real ticket, three sessions' outputs differed raw and were identical
after normalization.

## Cross-session reuse

Before reserving a provider call, the independent engine looks for a completed
`yes` or `no` for the byte-identical packet in the ticket's earlier sessions. It
reuses one only when:

- that session is listed by the controller, which admits only sessions whose
  reviewer-facing files (role prompt, reviewer schema, renderer, dispatcher and
  contract validator) have byte-identical recorded hashes;
- the reviewer settings and rubric match, since both are part of the answer key;
- the origin receipt still validates, artifacts included, in its own folder.

Reuse copies the artifacts and records `reused_from` (origin binding, key and
receipt hash) with no calls. A cache hit re-validates the origin. Abstentions and
blocked answers are never reused, reuse is not chained, and reusing a `no`
prevents re-asking identical evidence until it passes. Every new session still
requires the operator's authorization of its binding.

## Session bound

There is no fixed number of recovery sessions (see `INTERRUPTED-RESUME.md`): each
requires the operator's explicit authorization, and later sessions pay only for
questions whose evidence changed. Failed sessions are always retained.

Validation: synthetic tests in `tests/test-reviewer-reuse.py`, run by
`tests/test-recovery-independent.sh`.
