# Bounded operation repair

## Contract

The optional supervisor composes the existing independently callable operations.
A factory or Groom authorization must explicitly include
`{"bounded_repair":true}` in its attestation. Existing grants acquire no additional
authority. The browser offers the same selection and uses the same controller API.

The supervisor selects specification repair after a substantive adversarial
failure and implementation repair after substantive Verify or Review failures.
It retains the failed request, binding, signature, evidence, classification,
selected operation and allowance usage in a durable decision. Every selected step
has a persisted request ID before execution; replay and checkpoint recovery use
that identity. Concurrent supervisors cannot dispatch the same work twice.

Repairs consume the original operation and aggregate ceilings. No grant, deadline
or historical usage is reset. The existing three-failure gate ceiling remains;
retry classification reuses the existing infrastructure/substantive ledger.
Transport, malformed-response and unknown failures require an explicit repair
action rather than automatic runtime/configuration changes.

Failed test observations are retained with exact hashes and supplied to the
bounded repair worker. Missing, changed or oversized evidence blocks admission.
The worker cannot expand source scope or change controller authority. Unknown
change impact reruns all declared checks. Code repair is followed by full declared
Verify and independent Review; specification repair rebuilds the remaining Groom
contract first. A repair producing unchanged failed inputs stops before buying
another unchanged judgment.

Manual acceptance and publication remain independent explicit operations. A
supervised factory ends at independently reviewed evidence, with manual acceptance
pending. Current evidence is checked on first completion and every replay.

## External implementation after exhaustion

Explicit adoption binds external author provenance and the changed source.
The adopted revision receives a bounded Verify/Review allowance without another
Implement dispatch. Original attempts, failures and usage remain retained.
Re-adopting unchanged failed content cannot purchase another identical judgment.
Changed source without adoption does not silently resume implementation.

## CLI

Use the existing `ops assess` and `ops authorize` commands, selecting the factory
or Groom recipe and supplying `--attestation '{"bounded_repair":true}'`.
Run the returned grant with `ops supervise` and its `--grant` value. Ordinary
factory entry also selects the supervisor only for an explicitly repair-authorized
grant. `ops chain` retains its existing stop-on-failure behavior.

## Verification scope

All implementation fixtures use disposable repositories and synthetic providers.
Actual model quality, remote billing and production effects are not certified.
The optional supervisor does not add automatic infrastructure retries or an
implicit continuation allowance. Package graph scheduling is tracked separately
under #67; interruption reconciliation beyond existing checkpoints belongs #71.

## Sources

- `scripts/nightshift-operation-supervisor.py`: decisions and scheduling.
- `scripts/nightshift-operations.py`: authorization, evidence and execution.
- `scripts/nightshift-retry-budget.py`: retained retry classification.
- `tests/test-operation-supervisor.py` and
  `tests/test-operation-supervisor-review.py`: synthetic acceptance.
- `dashboard/src/operations.jsx` and `dashboard/test-browser.mjs`: shared controls.
