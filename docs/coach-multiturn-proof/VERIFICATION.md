# Offline verification

The initial multi-turn regression run failed three positive-admission tests with
`schema_string` because the original runtime rejected ordered conversation inputs.
The malformed-input rejection test already passed. This is schema/admission RED,
not a fabricated model-quality failure.

After implementation, seven multi-turn tests pass through the normal public
challenge, seal, run and gate APIs with an explicitly synthetic provider fixture.
Coverage includes actual prior assistant completion replay, two-turn final heldout
success, first- and second-turn failure, no partial acceptance, sealed-input
mutation, pre-launch whole-conversation budget admission, malformed turn arrays,
and transport unknown. Turn usage and reservation counts are checked.

The existing 25 proof tests passed, covering single-turn behavior, authentication
environment stripping, independent challenge, heldout exposure, retry gates,
ordinary evidence, concurrency and transport limits. No live provider was called
for this runtime repair; consumer live evidence is a separate task.

Test entry points: tests/test-behavior-multiturn.sh and tests/test-behavior-proof.sh.
