# Typed unittest verification

## Supported profile

An operation check can select `"adapter": "unittest-v1"` while retaining its
existing `id` and two-element `argv` with `python3` and the project test script.
The controller imports the test script through an isolated trusted runner and
loads standard unittest cases. Scripts must guard direct `unittest.main()` calls
with `if __name__ == '__main__'`. Unsupported adapter names or command types block.
Existing checks without an adapter retain the explicitly labelled `legacy-log-v1`
wrapper profile. Legacy log counts are not typed evidence. No pytest, npm or other
ecosystem adapter is certified by this change.

## Evidence contract

The runner persists versioned lifecycle receipts before, during and after tests.
Parent validation requires completed execution, distinct test identities,
consistent outcomes, successful termination and at least one useful passed test.
Failures, unexpected successes, no tests, all skips/expected failures, partial
execution, malformed records and timeout block Verify. Mixed passing/skipped
subtests remain valid; all-skipped subtests do not count as useful passes.
Printed summaries never establish typed success. Independent Review still judges
assertion adequacy; this runner is not a sandbox for malicious Python code.

Normalized observations retain the existing fields consumed by Review, repair
and semantic mapping. Typed observations add validated receipt/count/status data,
separate original raw output/hash and controller-rendered semantic evidence.
Raw logs and receipts are retained as content-addressed files in the private
operation ledger and included in evidence hashes. The aggregate observation
projection is bounded; oversized evidence fails explicitly, keeps originals and
identifies checks not executed. No oversized success is silently truncated.

Verification dependencies include source/test bytes and modes, effective sanitized
execution environment, declared overrides, actual selected Python/unittest
identity, adapter code and process-supervisor code. Changes invalidate affected
results. CLI and browser use the same Verify API and retain failed observations.
No provider call is added by the adapter; existing review/provider accounting
continues unchanged.

## Validation and integration

Code revision: `5fd0a3b70d464d025d19b481f221a4c7a3053968`.
Fourteen independent tests cover positive/negative assertions, forged summaries,
skips/subtests, malformed receipts, timeout/partial execution, replay, dependency
drift, semantic mapping and oversized evidence preservation. Exact final core and
browser evidence is recorded in `TYPED-VERIFICATION-VALIDATION.json`.

This focused candidate builds on the semantic provenance stack. Integration with
subsequent acceptance and cancellation PRs remains a separate exact-head check.
Issue 72 stays open until supported-profile integrated acceptance is complete.
Live-provider, fresh-machine and other endpoint certification remain unverified.
No installed runtime, real-ticket allowance, merge or deployment changed.

## Repository verification checklist

- PASS: Installed helper names retain the prefix; shared roles remain neutral.
- PASS: Upstream identity remains distinct from local evidence storage.
- PASS: Independent boundary tests and actual browser/CLI fixtures cover this profile.
- UNCHANGED: No trajectory schema change.
- PASS: Documentation cites source and exact fixture revisions; graph grounding is unavailable.
- PASS: Unsupported adapters and unknown live usage remain explicit.
