# Interrupted sessions and no fixed session count

Slice 7 of the semantic-review cascade on #65, prompted by a live run whose
controller process ended while a reviewer call was in flight.

## Resume after interruption

A session can be left `running` with a `pending` step and an unfinished decision
record when its controller process ends. The controller lock is an exclusive,
non-blocking OS lock held for the whole run and released when the process ends,
so when `resume` acquires it for a session recorded as `running`, that run is
provably not alive. For decision-based (compact) sessions, `resume` then:

- retains the interrupted step under `interruptions` and reruns that stage;
- retains each unfinished decision record (and its artifacts except the packet)
  as `<key>.interrupted-N.*`, never rewriting it;
- re-keys all calls of a retired record so a fresh attempt can reserve; calls
  whose outcome was never recorded are marked `interrupted`; every call stays
  counted against the allowance;
- asks that question again; completed answers are reused from the cache.

The dead process never finalized its active time for the interrupted stage, so that
partial time is not credited to `active_used`; the wall-clock deadline still ran
through it and is not extended.

`authorize` never recovers, and the legacy stage-runner mode keeps its original rule
(an interrupted stage is never relaunched). The session binding covers the runtime, so an
interrupted session can only be resumed by the runtime it was authorized with.

## Closing dead sessions

When a new session is authorized, any session still recorded as `running` belongs
to a controller that is no longer alive (the lock is held). It is closed as
`interrupted` (`superseded_by`, `closed_at`, reason `controller_process_ended`),
retained, and never rerun. The new session reuses its completed answers when the
packets and reviewer framing are identical.

## No fixed session count

The per-ticket session cap is removed. Every session requires the operator's
explicit authorization of its binding and limits, and later sessions pay only for
questions whose evidence changed, so a count limit added no protection. The
dashboard shows a closed session as "Recovery interrupted · superseded".

Validation: `tests/test-operator-escalation.py` (interrupted resume, dead-session
closing with answer reuse, no session count) and the Jev-mode interrupted
escalation in `tests/test-deterministic-evidence.py`.
