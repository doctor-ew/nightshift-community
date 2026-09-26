# Integrated operation assessment

## Implementation

This candidate combines repository-bound intake, provenance-bound semantic
handoffs, retained clarification decisions, manual case acceptance and typed
unittest verification from PRs 93–97. Nested decision assessment reuses the
already inspected context within the same assessment. Each new assessment still
inspects current source and execution identity; no persistent identity cache is
introduced. Standalone decision calls retain fresh context inspection.

## Integration evidence

The combined baseline at `1f16c53239dd06aacde25355bb0786b7ad93bed6` passed
155 operation tests across 18 suites. The final code candidate at
`5800c44dc1d978a85b02197c1cef32c7bf4deac0` passed 24 core tests and the actual
Chromium launcher/browser journey. Four independent context regressions passed.
The source and environment drift checks still invalidate prior evidence.

The synthetic completed-view sample decreased from 5.9947 to 2.0918 seconds,
with interpreter identity probes reduced from 59 to 10. This is one fixture
measurement, not a general latency guarantee. The browser fixture now uses a
guarded unittest entry point for both typed tickets and a longer harness timeout;
product execution budgets are unchanged. Earlier combined browser runs failed
on the harness timeout and an unguarded fixture entry point. Those logs remain
retained locally; neither failure is counted as acceptance.

The final browser journey made 13 synthetic provider calls: four for the initial
ticket, eight through bounded repair exhaustion, and one independent review after
external implementation. Replay made zero calls. There was no repeated Implement
after external adoption. Request sizes, separate allowance accounting, exact
revision and browser version appear in `INTEGRATED-ASSESSMENT-VALIDATION.json`.
Synthetic accounting has zero unknown reservations. Tokens, provider cache usage
and billing remain unknown. Elapsed synthetic execution is not provider latency.

## Certification boundary

This integrates PRs 93–97; cancellation/reconciliation under issue 71 and reviewed
commit/PR/CI delivery under issue 73 are not included. All fixtures use synthetic
providers and disposable repositories. No real ticket, live allowance, installed
runtime, merge or deployment changed. Issues remain open pending their complete
acceptance. Live certification requires a separately reviewed activation proposal.

## Repository verification checklist

- PASS: Runtime-neutral operations and configurable providers are preserved.
- PASS: Independent review, core regressions and browser acceptance passed.
- PASS: Source drift and execution identity remain part of evidence bindings.
- UNCHANGED: No trajectory schema change.
- PASS: Exact revisions and request accounting accompany integration evidence.
- UNVERIFIED: Live endpoint certification and remaining roadmap integration.
