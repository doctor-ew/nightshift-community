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
