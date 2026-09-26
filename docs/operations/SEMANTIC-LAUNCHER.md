# Spawned semantic transport acceptance

## Implementation

The operations controller loads the HTTP adapter dynamically. The prior
multiprocessing target used that temporary module name, which a spawned Python
interpreter could not import. Actual launcher execution raised a pickling error
before contacting the evaluator; in-process synthetic transports did not expose
this failure.

The bounded subprocess now enters the trusted adapter source through the standard
library run-path function. Transport arguments remain private IPC, not process
arguments. Existing HTTP response limits and timeout cleanup remain enforced.
Process construction and startup failures close both pipe endpoints and report a
stable failure without request contents. The ordinary efficiency CLI is unchanged.
Changed evaluator source invalidates earlier semantic receipts under the existing
source identity binding; it does not renew allowance.

## Integration evidence

Exact code: `7ad8ced7ef7e63f2150bc83dab85c484537bc37c`.
Five transport regressions pass, including actual launcher and Chromium execution,
replay, endpoint identity drift, timeout cleanup, oversized responses, HTTP errors,
repeated dynamic imports and injected process startup failures. Independent
negative control against the original implementation fails all five tests.
The existing 23 efficiency tests also pass.

The actual browser Groom recipe contacted only a loopback synthetic evaluator:
three semantic requests and five synthetic worker calls, including three required
independent escalations. CLI and browser replay added zero calls and reused four
operation receipts. Reload retained the semantic judgments. Exact request sizes,
Chromium version, elapsed fixture accounting and revision are recorded in
`SEMANTIC-LAUNCHER-VALIDATION.json`. Accounting has zero unknown reservations;
provider token usage, provider cache and billing remain unknown. No new evaluator
cache hits are claimed for operation-receipt replay.

## Certification boundary

This tests optional preparation handoffs through the actual HTTP boundary. Review
handoff mapping and semantic cache correctness retain their separate regression
evidence. It does not establish live semantic accuracy, calibration or savings.
No real provider, ticket restart, live allowance, installed runtime, merge or
deployment changed. Issue 68 remains open for complete integrated acceptance.

## Repository verification checklist

- PASS: Installed names and runtime-neutral configurable provider routing remain.
- PASS: Upstream identity and local controller evidence remain separate.
- PASS: Actual synthetic launcher/browser and existing efficiency tests pass.
- UNCHANGED: No trajectory schema change.
- PASS: Exact source and retained request evidence support the claims.
- UNVERIFIED: Live endpoint certification, semantic accuracy and cost savings.

## Typed/cancellation integration and interrupted startup

Runtime `683c2f65bf2af1d932b6ab106fd50af7f7cb1af9` integrates the #102
transport on #103's typed/cancellation/acceptance stack. Independent review found
an additional interruption window after process ownership but before the startup
flag was set. Cleanup now checks actual owned process identity and closes both
pipe endpoints even when cleanup fails. No arbitrary PID lookup is used.

Seven transport tests, 23 existing efficiency tests and six semantic-cache tests
pass. Actual Chromium reaches the loopback evaluator through the shared launcher:
three evaluator requests, five synthetic workers including three independent
escalations, zero replay calls and four reused operation receipts. Exact separate
accounting and request sizes are appended as `integrated_followup` in
`SEMANTIC-LAUNCHER-VALIDATION.json`. No additional live certification is claimed.
