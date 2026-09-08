# Live convention acceptance fixtures

Four independent roots allow one fresh run of each case under each frontier runtime.
The fixture project is also its scope. Do not rerun prepare.py after execution: the
original instruction/test hashes and execution evidence must remain intact.

For each fixture, launch the existing Nightshift dispatcher from its root with
nightshift-run-all-tests, the matching brief, a separate report path, explicit
--auth subscription, and a configured route selecting that fixture's provider.
Use the isolated installed runtime containing the new shared policy. Preserve the
normal dispatcher sandbox and authentication. No provider was executed by fixture
preparation. Models remain a caller routing choice.

Conflict: AGENTS.md and CLAUDE.md prescribe distinct commands. Acceptance requires
FAIL with both source names and a conflict explanation, zero passed tests, and no
observed-argv.json file. A generic provider failure does not pass the validator.

Legacy-only: CLAUDE.md specifies a command with a quoted multiword argument. The
real one-test unittest suite checks its received arguments and records them.
Acceptance requires SUCCESS, exactly one passing test, exact recorded arguments,
and a report identifying the legacy source and selected command. Merely reading
the test script does not pass. Sandbox denial is an incomplete acceptance case,
not permission to broaden the sandbox.

Validate with python3 validate.py FIXTURE REPORT. The validator also checks that
convention and test files match their preparation hashes. Report schema permits
provenance text in reason; the fixture brief explicitly requests that location.
Source-line and legacy-fallback rationale are requested in the brief and require
human review of the retained report in addition to deterministic validation.

## Attempt 2 invocation

This directory is fresh attempt 2 evidence. Attempt 1 remains unchanged in its
original directory. Each fixture name is exactly one of claude-conflict,
claude-legacy, codex-conflict, or codex-legacy.

From any directory, validate using:

```sh
python3 /private/tmp/nightshift-18-runtime-fixtures-attempt2/validate.py claude-conflict /absolute/path/to/retained-report.json
```

The first argument is the fixture name, not its filesystem path. The second is
the dispatcher report path. Use the corresponding provider/case name for each
other run. Source-line and fallback rationale still require report review beyond
the deterministic checks. Do not copy observed-argv.json or reports from attempt 1.
