# Operator escalation instead of ending the session

Slice 3 of the semantic-review cascade on #65. Operator decision: an independent
LLM reviews uncertain answers first; when it abstains, contradicts the primary
judgment, or still cannot ground a yes after its single re-ask, the question goes
to the operator. Manual cases always stay with the operator.

## Behavior

When a decision ends with `decision_abstained`, `decision_reviewer_contradiction`
or `decision_independent_evidence_incomplete`, the recovery session enters
`awaiting_operator` instead of `blocked`. The session records exactly which
question is awaited (`awaiting`: stage, packet ID, packet hash, blocked receipt
hash, reason), and the summary shows it. A clear `no` is not escalated.

The operator answers with:

```
nightshift-controller-recovery.py operator-decide <ref> --expected <binding> \
  --packet <awaited packet sha256> --decision yes|no --reason "<why>" --operator "<identity>"
```

The record is bound to the session binding, the exact packet, and the blocked
receipt. Each question can be decided once. No provider call is made.

`resume` then reruns only the waiting stage. Every other answer is served from
the cache, the decided question is not re-asked, and a `no` fails the gate
(`operator_rejected`). Time spent waiting is not run time: on resume the
wall-clock deadline is extended by exactly the pause, which is listed in
`allowance.operator_pauses`. Earlier waiting steps are retained in
`operator_waits`, and decisions in `operator_decisions` (with record hashes).

Acceptance re-validates operator-decided questions: the stored receipt must still
be a valid blocked receipt with an escalation reason, and the decision record must
match its recorded hash, the binding, the packet and the receipt.

Validation: `tests/test-operator-escalation.py` (6 synthetic tests, run by
`tests/test-recovery-independent.sh`).

## Dashboard

Slice 5. A session waiting for the operator shows **Waiting for your decision**
with the stage, the question ID and the reason, and the exact `operator-decide`
command (binding and packet hash filled in; the operator supplies decision,
reason and identity). The command is shown only when both hashes are well-formed.
The call count is broken down by kind (for example `jev`, `independent`, `reask`,
`exception`, `shadow`), and a waiting stage reads "waiting for your decision". The
dashboard does not record decisions itself; that stays a deliberate CLI action.
