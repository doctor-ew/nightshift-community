# Stage failure diagnostics

## Implementation

Stage receipt templates encode task identifiers as JSON strings. The controller
strictly validates receipt identity and schema, including duplicate keys and
malformed or deeply nested JSON. Invalid receipts remain failed evidence.
Bounded private diagnostic sidecars retain precise validation errors and reported
worker findings under the UNVALIDATED_WORKER_DIAGNOSTIC label. These findings do
not enter authoritative stage findings or establish completion. Nonzero worker
exits retain transport accounting.

Claude subscription status checks distinguish explicit logout from missing CLI,
execution denial, timeout, malformed output and other inconclusive probes. Probe
output is bounded to 32 KiB and five seconds. Sanitized diagnostics retain
categories and counts, excluding raw authentication output. No fallback provider
or permission bypass is introduced.

The dashboard renders bounded diagnostic text without executable markup. Resume
and time continuation use canonical pipeline state and stage retry ledgers,
including stale views and recognized inspection or question states. The server
checks exhaustion again after preflight, immediately before allowance mutation
or process creation. Additional wall time cannot replenish stage retries.
Explicit recovery remains a separate operation.

## Integration validation

Base revision: 717e74e06292436442f09d24725a645061f8004b.

- Receipt diagnostics: 12 tests passed; existing pipeline: six tests passed.
- Authentication diagnostics: 14 tests passed; dispatcher: 130 assertions passed.
- Console continuation: nine tests passed, including duplicate requests, stale
  display state, answered questions and exhaustion during preflight. Rejections
  preserve allowance bytes and launch no worker.
- Dashboard model: 17 tests passed. The actual built dashboard passed a synthetic
  browser test at desktop and mobile sizes, including escaped diagnostic content
  and disabled exhausted-stage controls. Eight intercepted GET requests, zero
  provider calls, no browser errors. This fixture has no model usage or cache
  reuse to report; it does not measure live provider accounting.
- Independent design and code review approved the final changes.

The receipt and authentication suites are included in the architecture harness;
the synthetic browser test runs in the existing dashboard CI job. Full hosted
CI must be evaluated on the published revision separately.

## Certification boundary

These checks use disposable repositories and synthetic providers. They do not
certify live subscription execution, approve external transfers, reset retained
retry counters, activate an installed runtime, merge or deploy. Historical
receipts and failed-run evidence are not rewritten. An inconclusive probe does
not establish either login success or logout. Endpoint-specific permission and
live certification remain outstanding under the roadmap.
