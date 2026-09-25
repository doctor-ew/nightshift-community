# Synthetic acceptance report

The candidate is based on PR #61 at `69763060dfbdac23797434f7172599116ea643f2`.
At implementation time, #61 remained an open draft based on #60; #60 depended on
#56, which depended on #50. None was assumed merged. The controller is published
in [PR #63](https://github.com/doctor-ew/nightshift-community/pull/63).

## Acceptance coverage

The four new suites contain 38 passing tests: 24 controller, 3 compact semantic,
7 independent-review regressions and 4 executable interface tests. Providers,
repositories, identities, publication remotes and ticket artifacts are synthetic.

| Requirement | Executed coverage |
| --- | --- |
| Independent operations and Groom suboperations | Read-only preflight; missing prerequisites; direct operation execution; explicit acceptance and publication to a temporary local remote |
| Standalone and chained equivalence | Equivalent gate outcomes and dependency evidence; actual patch integration and verification; legacy ticket entry selects the same authorized recipe |
| Exhaustion followed by external implementation | Classification exhaustion preserves draft and findings; external adoption, verification and independent review perform no implementation dispatch; acceptance remains pending |
| Duplicate requests and safe restart | Concurrent requests, duplicate grants, replay, interrupted subprocess, unknown reservation, completed-worker reconciliation and checkpoint tampering |
| Selective stale-evidence rejection | Source, specification, scenarios, rules, architecture, environment, route and reviewer-policy changes; unresolved findings, contradictory judgments, missing evidence, empty/all-skipped tests |
| Bounded and exact-once accounting | Per-operation and aggregate ceilings, overrun rejection, sequential/parallel execution, interrupted calls, no charge for rejected preflight, immutable migrated ledgers |
| Shared clients | Real shell and fish commands compared with the dashboard HTTP API, including failure reasons, admission and next actions; CSRF rejection; duplicate execution |
| Compact decisions | Exact mapping and raw observation validation, pinned configuration, missing-context rejection, abstention/risk escalation, durable cache reuse |

The independent reviewer supplied seven regression tests and reported no remaining
blocker in the audited changes. The final combined run passed all 38 tests against the completed implementation,
including the accepted-architecture packet follow-up. Detailed counts and
measurements are retained in `CORE-VALIDATION.json` and `INTERFACE-VALIDATION.json`.

Existing decision, recovery, pipeline, continuation, budget, chat, repair,
architecture, provider-policy, dispatch, CLI, manifest, setup and release-input
regressions passed. Temporary installation inventory tests and routing-path tests
also passed. Dashboard HTTP tests passed (11), dashboard model tests passed (14),
and the current dashboard bundle rebuilt successfully. ShellCheck at warning
severity and whitespace checks passed.

## Measurements

The synthetic factory dispatched four provider processes. Captured prompt/schema
argument sizes were 3,073, 6,195, 3,340 and 6,670 bytes. Their controller packets were
650, 731, 917 and 1,206 bytes. Replay reused seven operation results with no additional
provider call. Measured provider execution was 1.559 seconds; wall duration was
6.730 seconds; unknown reserved execution was zero. These are captured executable
arguments and controller payloads, not wire-level HTTP sizes or model token counts.

The semantic fixture made three Jev calls with request sizes of 2,638, 2,621 and
2,619 bytes, two independent escalations and three cache hits. Including mandatory
substantial review, that fixture recorded six calls and approximately 0.003 seconds
of in-memory synthetic execution. These fixtures do not demonstrate live accuracy,
calibrated confidence, cost savings or real-ticket delivery.

## Integration limits

Automated Chromium browser execution now passes against the actual built UI and
HTTP server with isolated synthetic providers. Eleven checks cover admission and
CLI parity, recipe execution, replay, explicit acceptance, source drift, adoption,
failed verification, blocked review, reload persistence and desktop/mobile rendering.
See `BROWSER-VALIDATION.json` and the adjacent screenshots. A fresh headless profile
was used; the operator's connected browser was unavailable and was not modified.

The inspected PR #61 CI run reported 41 passing suites and six failures. Locally,
`tests/test-factory-auth.sh` exited 65 and `tests/test-factory-preflight.sh` exited 1
with the same outcomes on both the candidate and an untouched PR #61 worktree.
Follow-up fixes make all six inherited suites pass locally: explicit stage fixtures
replace obsolete monolithic-worker expectations, synthetic routes are pinned, homes
are isolated, and the sealed trajectory recorder includes its required dependencies.
The new operation report-path failure is also fixed for Linux. Production gates and
the recorded trajectory baseline are unchanged. Full remote CI reruns are pending.

Issue #62 remains open for integrated acceptance, including dependency-stack integration and successful remote CI reruns. `ROLLOUT.md` proposes separate live validation;
no live provider, real ticket, installed runtime, merge or deployment was invoked.
Operator checkout changes and retained ticket evidence were preserved. A CX port
is a later task; no private configuration or ticket evidence is included here.
