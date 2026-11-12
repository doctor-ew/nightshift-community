# Product interruption: causal trace

The first Product attempt wrote a spec and scenarios, then returned a failed receipt without dispatching the required independent reviewer. The controller's ordinary substantive-repair loop covered reviewer stages but returned immediately for a Product failure.

## Manual requirement origin

The stage prompt in `scripts/nightshift-factory.sh` unconditionally instructed the worker: “Keep required manual acceptance pending while completing automated work.”

The retained Product command created required case C-7 as manual and supplied this authorization: “Issue 154 requires isolated installed end-to-end acceptance; current task explicitly says to keep required manual acceptance pending.” The Product handoff contained no operator decisions requiring manual acceptance. The public issue requires an isolated live run; it does not assign that acceptance to a human-only procedure.

The scenario validator in `scripts/nightshift-behavior-proof.py` accepted any nonempty owner, authorization and procedure strings. It did not establish the authorization's origin. `tests/test-factory-auth.sh` explicitly asserted the unconditional launcher wording.

This is a concrete instruction-to-artifact propagation and validation defect. The conditional instruction in `commands/nightshift-spec.md`—manual cases apply when the operator explicitly owns an external check—was not enforced by that free-text contract.

## Repair

The launcher now distinguishes explicitly human-owned checks from automated live acceptance and states that generic workflow guidance cannot authorize a manual case. The corresponding launcher regression asserts that distinction. Manual authorization now binds to an answered recorded operator decision, its response digest and an exact quotation; free-form legacy authorization requires explicit reconciliation. Existing receipts are retained. Product scenarios were repaired from actual independent reviewer findings, and a later independent report approved their observable positive and negative coverage. That approval is design evidence, not execution certification.

The controller now schedules scoped ordinary substantive repairs for author stages as well as reviewer stages, retaining findings, previous receipts and input identities. Failed unchanged repair inputs remain a diagnosis signal; the controlling agent must resolve the cause rather than declare the work complete.

Sources: `scripts/nightshift-factory.sh`, `scripts/nightshift-pipeline.py`, `scripts/nightshift-behavior-proof.py`, `commands/nightshift-spec.md`, `tests/test-factory-auth.sh`, `tests/test-pipeline.py`; retained Product attempt and handoff for task 154.
