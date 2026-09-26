# Typed verification integration

## Supported profiles

Verify uses versioned runner observations through the existing operation API.
The plan check still requires `id` and a two-element `argv`; optional `adapter`
selects a compatible profile. Without that field, the executable selects the
profile:

| Executable | Adapter | Admission evidence |
| --- | --- | --- |
| `python3` | `python-unittest-v1` | Completed unittest runner and per-test lifecycles |
| `node` | `node-test-v1` | Per-file framework summaries plus completed global runner |
| `bash` | `legacy-wrapper-v1` | Retained raw execution; cannot certify typed Verify |

`unittest-v1` and `legacy-log-v1` are accepted compatibility names from #96.
Python lifecycle, skipped-subtest handling, strict duplicate parsing, runtime
identity and bounded evidence handling reuse the #96 implementation concepts.
The integrated adapter preserves normal `__main__` execution and arguments. If a
script completes without invoking an instrumented runner, unittest discovery uses
its resulting namespace. Custom result classes are replaced with the trusted
result recorder; arbitrary custom runners are not certified as their own runner.
Stdlib unittest loads before project imports. This is a framework observation
boundary, not a sandbox against deliberately malicious test code. Independent
Review remains responsible for oracle adequacy.

Node counts only per-file framework summaries. A successful file envelope without
registered tests is not a useful test. Stdout and stderr, including forged TAP or
unittest summaries, never determine counts. A runner version without the required
summary events is blocked instead of inferred from printed output.

## Validity and retention

A successful check requires the exact invocation binding, a complete receipt,
consistent nonnegative typed counts, successful process exit and at least one
useful passed test. Skipped, expected-failure and TODO-only runs are vacuous.
Failure, unexpected success, abrupt exit, malformed evidence and partial timeout
cannot pass. Python test identities must be unique. Duplicate JSON keys and
boolean count/version substitutes are rejected.

Bindings include current source modes and hashes, declared checks, effective
bounded environment, executable identities, Python unittest identity, adapter
source and supervisor source. Changed evidence invalidates downstream acceptance.
The runner uses the existing cancellation and deadline supervisor. Raw logs,
typed receipts and partial observations remain outside disposable source copies.
Oversized output remains retained but blocks bounded operation/semantic admission;
no truncated output can certify success. Replays reuse current receipts without
repeating implementation or provider calls.

Legacy wrappers remain executable. To obtain typed acceptance, declare the
underlying supported checks explicitly. Other test ecosystems require another
reviewed adapter; the controller reports the unsupported boundary. CLI and browser
use the same admission path, and the browser exposes typed counts and retained
raw evidence references.

## Certification boundary

All fixtures use disposable repositories and synthetic providers. The local
Python and Node profiles require separate live endpoint certification before a
real factory run. Provider configuration remains unchanged. No installed runtime,
real ticket, live allowance, provider, merge or deployment is used by this work.
