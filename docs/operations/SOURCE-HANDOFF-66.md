# Fresh source-reference handoff

## Implementation

Product now passes the original source reference into child launcher admission.
Later stages continue to pass the canonical task key. Existing task, budget,
receipt, decision and worktree bindings are unchanged.

Baseline: PR #64, `afe619c1c7f116d937a1d0709d60216a9133ae1c`.
Dependency stack: #50 → #56 → #60 → #61 → #63 → #64.
This fix is stacked on #64; no prerequisite PR was merged or rewritten.

## Synthetic verification

`python3 tests/test-pipeline.py` passes six tests. Before the fix, all four
fresh-reference cases failed with `INPUT_RESOLUTION_REQUIRED`. After the fix,
Jira, repository-qualified GitHub, prefixed local Markdown and bare local
Markdown paths containing spaces pass baseline/input admission and stop at
`MANIFEST_MISSING`, before authentication or provider dispatch.

The regression runs the actual child launcher in disposable repositories.
Disposable provider/network sentinels record zero invocations. Canonical task
identity is checked; existing budget and stored decision bytes are identical.
Retained downstream input remains admitted when the original source is absent.
The existing suite covers restart, retained evidence, stale evidence, unchanged
findings, manual acceptance and scoped publication to a disposable local remote.

An independent agent reviewed the design and production diff, hardened the
regression with sentinels, and reran the admission test. No blocker remained.

The first restricted-sandbox full-suite run failed on denied shell process
substitution. The same synthetic suite passed with that facility available:
six tests in 43.251 seconds. This is test-environment evidence, not live quality.

## Accounting and release status

Fresh-admission fixture: zero provider calls; request bytes, cache reuse and
provider execution usage are not applicable because admission stops before
dispatch. Existing synthetic worker fixtures use disposable executables.
No real provider usage or billing was incurred by this regression.

Implementation is a review candidate. Integration into the default branch,
installed activation and live certification remain pending. No operator runtime,
real ticket, live allowance, private configuration or retained evidence changed.

## Sources

- `scripts/nightshift-pipeline.py`: Product argument and canonical bindings.
- `scripts/nightshift-factory.sh`: actual child admission.
- `scripts/nightshift-ticket-source.sh`: source identity derivation.
- `tests/test-pipeline.py`: red/green and retained-state regressions.
