# Explicit acceptance of retained recovery

## Controller contract

Recovery finishes its deterministic verification and independent adoption, review,
drift and QA gates before entering `pending_manual_acceptance`. Explicit acceptance
is a separate, zero-provider controller operation. It grants no allowance and does
not rewrite original failures, stage budgets or legacy behavior-proof records.

Use `nightshift recover accept <retained-ref> --project <project> --expected
<assessment-sha256> --operator <operator> --attestation <json-file>`. The JSON file
binds the exact recovery assessment. If there are no manual cases, it contains
`binding` and `accepted: true`. Otherwise it contains `binding` and `cases`; each
case requires `id`, `case_sha256`, `passed: true`, `observation` and `evidence`.
`case_sha256` hashes the complete bound scenario case, including its procedure and
acceptance criteria, using the controller's canonical digest. Observations and
evidence must describe the operator's actual acceptance; test exits cannot stand
in for manual approval.

The browser controller API exposes the same operation at
`POST /api/tickets/recovery-accept`, with `task`, current settings `sha256`,
`assessment_sha256`, `operator` and `attestation`. CLI and API use the same action
and controller locks and validation. The existing dashboard observes completion;
it does not synthesize manual observations.

## Evidence and durability

Before acceptance, the controller reopens the exact current source, mode, route,
verification output, every independent gate receipt and every adopted stage
receipt. Missing, changed, failed or incomplete evidence blocks acceptance.
The same per-case attestation policy is shared with standalone operations.

The controller writes an immutable acceptance receipt before atomically marking
the recovery session and ticket complete. An identical request can finish a crash
between those writes and replay the completed result. Changed operator or
attestation data conflicts; it cannot replace the receipt. An incomplete receipt
fails closed and remains retained. Subsequent dashboard evidence validation checks
acceptance integrity as well as source and gate evidence; stale evidence is not
presented as current completion.

## Certification boundary

Validation uses synthetic providers and disposable repositories. No live provider,
retained ticket, installed runtime, grant, merge or deployment is needed to test
this operation. Live acceptance remains an explicit operator action against its
current assessment and actual manual observations.

The reviewer child process remains bound to the executing Community source and the
bound provider policy. A stricter inherited provider policy remains effective;
invalid policy values fail before dispatch. The role-child guard is preserved,
and subscription authentication retains the existing user home. Synthetic tests
use poisoned default configuration to detect accidental runtime fallback without
reading any operator configuration.

Focused verification includes the standalone operations acceptance regression,
15 existing controller tests, four console adapter tests, dashboard authentication
checks and nested-attestation HTTP transport checks. Independent adversarial
coverage is in `tests/test-recovery-acceptance-review.py`; reviewer environment
coverage is in `tests/test-recovery-reviewer-environment.py`. Both run through the
existing `tests/test-recovery-independent.sh` offline entry point.

## Validation

Independent design/code review approved the final implementation. All 78 focused
checks passed: 15 acceptance, 27 independent recovery, four reviewer-environment,
15 legacy controller, four console, one Operations acceptance, 11 dashboard server
and one additional HTTP transport check. Tests exercise actual CLI and real
loopback HTTP/controller acceptance, current completion views, exact replay,
receipt publication crashes, stale/tampered evidence and fixture-mode rejection.
Acceptance adds zero provider calls or allowance and preserves original failed
attempts and budgets. Broad Operations testing was interrupted after partial
progress and is not claimed as passed; full hosted CI remains pending.

Reviewer dispatch now binds the executing runtime home and composes bound and
inherited provider policy without relaxing stricter restrictions. Subscription
HOME and the nested-role guard remain intact; invalid policy fails before dispatch.
Disposable poisoned-default and actual synthetic-dispatcher checks passed.
