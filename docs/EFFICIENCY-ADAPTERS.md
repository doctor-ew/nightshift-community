# Efficiency adapters

Nightshift provides `exec` for captured command output and `evaluate` for optional
Jev shadow evaluation. Both default on; neither can approve a gate or replace
independent review. Azure and automatic tool/browser routing are outside this adapter.

## Installation and commands

Use the normal Nightshift installation/update procedure. The Python helper needs
Python 3.9+ and its standard library on macOS/Linux (POSIX dirfd, O_NOFOLLOW,
and process-group support). Native Windows reports `UNSUPPORTED_PLATFORM`: evaluation remains observational
(exit 0), while command capture is rejected (exit 69). Install RTK separately from
[its official project](https://github.com/rtk-ai/rtk) and put `rtk` on PATH.
The adapter uses `rtk pipe --filter NAME`; older binaries without this interface
fall back to captured raw output. No global hooks are installed.

```sh
nightshift exec -- python3 -m pytest tests/
nightshift exec --no-enabled -- cargo test
python3 /path/to/nightshift/scripts/nightshift-efficiency.py exec -- git status
nightshift evaluate --input ./approved-evidence.txt
nightshift evaluate --no-enabled
```

The factory dispatches these commands before update/output wrappers. Role workers
use the helper directly because the recursive factory guard remains active.
At ordinary factory completion, evaluation runs observationally and preserves the
provider's exit code. Without `NIGHTSHIFT_JEV_INPUT`, it writes a visible `NO_INPUT`
skip; it never searches for evidence. Workshop's separate runtime is not instrumented.

## Configuration

Precedence is invocation options, environment, project `.nightshift-efficiency.json`,
then shipped `efficiency.json` (installed as `nightshift-efficiency.json`). Unknown configuration fields and malformed section structure fail before execution/network.
Each adapter validates only its effective settings: unused Jev values cannot block
command capture, and unused capture settings cannot block evaluation. Credentials
are environment references only; no secret values belong in configuration.

```json
{
  "rtk": {"enabled": true, "timeout_seconds": 10},
  "exec": {"timeout_seconds": 900, "max_bytes": 67108864},
  "jev": {
    "enabled": true,
    "endpoint": "https://api.typesafe.ai/v1/systemone",
    "model": "jev-latest",
    "key_env": "TYPESAFE_API_KEY",
    "timeout_seconds": 20,
    "max_bytes": 262144,
    "allow_loopback": false
  }
}
```

Environment names are `NIGHTSHIFT_<SECTION>_<FIELD>`: for example
`NIGHTSHIFT_RTK_ENABLED=false`, `NIGHTSHIFT_JEV_ENABLED=false`,
`NIGHTSHIFT_EXEC_MAX_BYTES=1048576`, `NIGHTSHIFT_JEV_MODEL=jev-latest`.
Booleans/numbers use JSON literals. String fields are literal strings.
`--timeout-seconds` overrides the selected adapter's timeout; command execution
limits use project configuration or `NIGHTSHIFT_EXEC_*`.

For evaluation, set the referenced `TYPESAFE_API_KEY` in your environment and supply
an explicitly approved evidence file via `--input` or `NIGHTSHIFT_JEV_INPUT`.
This authorizes transmitting that file to the configured endpoint and may incur
provider charges. No input or key means no network. `--endpoint`, `--model`,
`--key-env`, `--max-bytes`, and `--allow-loopback` override Jev settings. HTTPS is
required except explicitly allowed HTTP loopback fixtures. Redirects are rejected.

## Capture contract and limits

The conservative allowlist is direct `pytest`/`pytest3`, `python[3] -m pytest`,
`cargo test`, `tsc`, `vitest run`, and human-readable `git status`. npm wrappers,
source reads, diffs, shell strings and all other commands bypass compression.
JSON/NUL/XML/reporter/format/machine flags and exact listing modes (including
`tsc --listFilesOnly`, `pytest --collect-only`, and `cargo test -- --list`) bypass
compression; observed NUL and
JSON-like output bypass too. Nonzero command exits always return raw stdout.
Only stdout is filtered; stderr is retained and returned separately.

The original argv executes once without shell reinterpretation. Missing RTK,
filter failure, timeout, empty/invalid UTF-8/NUL output or larger output returns
the already captured raw bytes. A filter does not prove semantic equivalence:
review exact claims against raw artifacts.

Command capture defaults to 900 seconds and 64 MiB total stdout+stderr. Hitting a
bound retains the allowed byte prefix, kills the process group, returns 124 and
marks `raw_complete=false`; such
receipts are partial evidence, never normal command completion. Otherwise the
original exit code is preserved (signals use 128+signal). Output is buffered until
completion; interleaving and interactive terminal behavior are not preserved.
RTK defaults to 10 seconds. Jev defaults to 20 seconds total including process
startup/DNS/TLS/body, with 256 KiB input/request/response limits. No retries occur.

## Private evidence and accounting

Receipts default to `~/.nightshift/efficiency/<unique-id>/`; optionally set an
absolute `NIGHTSHIFT_EFFICIENCY_DIR`. The base must be private and owned by you.
Directory traversal rejects symlinks; unique directories are 0700 and files 0600.
Receipts are saved before output is forwarded. A closed consumer returns 141 and
a separate `delivery.json` records that delivery outcome, preserving the command
receipt and its actual return code.

Command receipts retain `stdout.raw`, `stderr.raw`, and separate filter artifacts,
stream hashes, bytes, exit status, measured latency, and fallback reason. Receipts
include implementation and effective-configuration hashes plus the parent run ID;
evaluation also hashes the configured endpoint identity. No raw argv or endpoint
credentials are written as provenance. Raw
command streams may contain whatever the original command emitted; keep them private.

Evaluation stores only hashes, versioned rubric identity, validated typed Noul
judgments, selected/reported model, nonnegative available usage, and elapsed time.
It never stores request/response bodies, keys, or server error content. Noul values
are rubric judgments, not confidence or PASS/FAIL authority. Missing usage/cost
remains unknown. Attempted Jev calls emit a bounded observation through the existing
metrics event interface before factory summary, with available usage and duration,
a `jev-shadow-` invocation ID, and null engineering stage/provider. Event success
means the diagnostic API call returned a valid response, never gate approval.
Skipped calls emit no model-usage observation. Selected/reported models remain
distinct in the shadow receipt. These observational events do not fabricate billed
amounts or independently establish complete ticket cost coverage. Byte reduction is not billed savings; existing accounting policy
in `NIGHTSHIFT-COST-POLICY.md` and `RUN-MEASUREMENTS.md` remains authoritative.

Artifacts are retained without automatic deletion. Cleanup is a separate explicit
operator action; the adapter does not delete receipts, rewrite history, or kill
unrelated processes. Only its own isolated capture process group is terminated
on cancellation, capture failure, or a configured bound.

## Verification and references

Run `bash tests/test-efficiency.sh` (the CI entrypoint for `python3 tests/test-efficiency.py`) for offline fixtures including local HTTP
mocks; these perform no paid provider calls. The [pinned RTK 0.49.0 smoke artifact](efficiency/rtk-smoke.json) covers synthetic
pytest, cargo-test, vitest, empty successful tsc output, and git-status samples.
It verifies those representative filter interfaces, not broad semantic equivalence
or real project savings. Offline fixtures also check every allowed mapping and
raw bypass for exact listings. Live Jev accuracy, empirical ticket
savings, and broad RTK command compatibility remain unverified follow-ups.

API contract: [Typesafe quickstart](https://docs.typesafe.ai/introduction/quickstart.md).
Capture interface: [RTK pipe implementation](https://github.com/rtk-ai/rtk/blob/develop/src/cmds/system/pipe_cmd.rs).
Code references for the examples/configuration: `efficiency.json:1`,
`scripts/nightshift-efficiency.py:41` (configuration),
`scripts/nightshift-factory.sh:26` (entrypoints).
