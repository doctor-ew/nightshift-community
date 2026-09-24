# Issue 35: local verification exhausted

Status: **FAILED**. Three smallest-scope verification repair cycles were used; the final full suite remains red. No delivery commit, push or pull request was made.

## Remaining failures

- `bash evals/run-tests.sh`: 37 suites passed, 1 failed. `tests/test-factory-cli.sh:90` requires verbose advisory calls to omit `--json`; unconditional factory JSON capture changes that behavior.
- ShellCheck: `scripts/nightshift-ticket-source.sh:81` triggers SC2034 because the local `task` variable is unused.

## Accepted evidence

The focused test role reports 103 explicitly counted passes and zero failures. Both provider-to-ticket integration fixtures pass. Final behavioral evidence covers all eight sealed scenarios. Independent Claude review approves the repaired source with warnings; that does not override the failed verification gate.

## Retained state

The existing worktree, branch, source edits, sealed specification/tests, role outputs, logs and historical retry receipts remain in place. Runtime routing is outside the feature changes. The earlier operator interruption is recorded separately and was not counted as failure. See `failure-receipt.json` for repair scopes, source locations and evidence hashes.
