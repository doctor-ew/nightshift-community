# Bounded operation repair

## Behavior

The shared `Operations.chain` controller persists its operation queue and cursor
inside the original authorization. CLI, dashboard and factory entry points use
this controller. Completed results are reused. A process interrupted after an
operation completes resumes its existing request before advancing the cursor.

Eligible failures in adversarial Groom select `groom-spec`; failed verification
or independent Review selects `implement`. The author receives concrete findings
and failed-evidence bindings. The controller then runs the remaining required
operations, including every declared verification check and independent Review.
There is no speculative change-impact exclusion of tests. Accept and Publish
remain separately authorized operations.

Repairs consume the original operation and aggregate limits and deadline. The
existing ceiling of three failed evaluations per gate remains conservative:
there can be at most two automatic repairs between those failures. No-op repairs
cannot purchase another unchanged evaluation. Transport, malformed responses,
unknown effects, changed authority and integration failures stop for inspection.
They do not authorize speculative source repair.

## External implementation

Explicit adoption of changed source binds external provenance before Verify and
Review. Historical attempts and charged calls remain intact. Verification of a
current adopted source uses its source-bound failure history; it does not inherit
a different implementation's validation exhaustion. Identical failed evidence
still blocks. Automatic repair retains its global failure ceiling. Adoption does
not create or renew an allowance, accept the work or publish it.

## Evidence

Failed verification retains its raw observation file and SHA-256. The worker
receives a bounded finding summary with check identity, outcome, raw-evidence
reference and hash, and a labeled output excerpt. Serialized summaries remain
within the existing worker finding limit, including escaped Unicode. Missing or
oversized required request context still blocks; no passing judgment is inferred
from a shortened log excerpt.

Synthetic regressions are in `tests/test-operation-healing.py` and independently
authored `tests/test-operation-healing-review.py`. They cover targeted repair,
no-op convergence, exhaustion, external adoption, crash after integration,
concurrent duplicate chains, stale evidence and large failure logs. Existing
operation, interface, installation and browser tests cover the reused boundaries.

## Certification limits

This is implementation of the shared-operation supervisor under #11. Live quality,
provider token/cache usage, billing, endpoint-specific drift/live QA and installed
activation remain unverified. Synthetic execution timing is not provider latency
or a cost saving. #11 and roadmap #65 remain open until their full acceptance is
met. Deployment and shared-service identity remain optional profiles.

## Review and measured run

Independent design/code review approved executor SHA-256
`151d56d7f696e6fcf09621137ed09836229639f103e6353c8e43d78c2933673d`.
The reviewer independently authored six passing regressions (39.071 seconds).
The four author regressions passed in 30.758 seconds. The actual Chromium fixture
passed all eleven browser checks with four synthetic executable calls.

`SELF-HEALING-MEASUREMENTS.json` records the same executor hash. Baseline: four
in-process synthetic worker calls, 3,563 packet bytes, 6.248 seconds wall time.
Fault/repair: five calls, 6,371 packet bytes, 7.358 seconds wall time. Both replays
reuse seven results without dispatch. These packet bytes exclude transport framing;
token usage, provider cache usage and billing remain null. No model escalation
occurred. These measurements establish accounting behavior, not live quality.

Verification checklist: installed prefixes and runtime-neutral roles are unchanged;
upstream identity remains separate from local state; existing and new fixtures
cover the operation boundary; no trajectory schema changed; scaffold claims cite
source files; live readiness and unsupported endpoints remain explicitly unverified.
