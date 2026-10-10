# Measured run estimate

Slice 6 of the semantic-review cascade on #65: allowances are proposed from
measurement, not picked. `assess --verify` now returns `run_estimate`. Nothing is
spent and nothing is applied; the operator still approves the binding and limits.

- `unique_questions`, `gate_evaluations`, `cache_reuses`: from the actual packets.
- `provider_calls.expected`: one call per unique question plus the escalations the
  policy makes even for confident answers (`planned_escalations`: the shadow sample,
  and for version 1 packets high-risk exceptions); both are deterministic per packet; `maximum` allows one escalation or re-ask per question.
- `estimated_input_tokens`: the same conservative estimator that enforces the token
  budget (Jev request bodies, or reviewer framing in independent mode).
- `observed_call_seconds`: median and maximum per call kind from calls this ticket
  has already made. With no observations it is empty and the proposed seconds are
  `null` (unknown), never invented.
- `proposed_limits`: calls = maximum (within the 64-call cap); seconds = slowest
  observed call × maximum calls (within the 3600 s cap).

Validation: `tests/test-deterministic-evidence.py`
(`test_run_estimate_is_measured_and_proposes_limits`).
