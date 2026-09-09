# Runtime multi-turn review

Reviewed commit e006f2bb254603c514954daf6db76359295cf22f and subsequent crash-window repair in /tmp/nightshift-coach-runtime-repair-20260909. Read-only review of product files; only this report and isolated synthetic reproducer artifacts written. No consumer private proof files or heldouts accessed.

## Finding corrected during review

P1: Persisted failed turns could be resampled after interruption. Original scripts/nightshift-behavior-proof.py:1220 saved a failed turn and its finalized budget before scripts/nightshift-behavior-proof.py:1254 appended the aggregate observation. Original retry guards at scripts/nightshift-behavior-proof.py:1118 consulted aggregate observations only. Interrupting in that gap allowed unchanged development prompts and unchanged failed heldouts to be sampled again, eventually returning proof_eligible.

Reproduced against clean archived e006f2b with /tmp/nightshift-runtime-crash-review-original.py: initial development and final each returned behavior_failed; after retaining the durable failed turn and budget but removing the not-yet-written aggregate, both resumed runs returned exit 0 proof_eligible. This changes only synthetic fixture state to model the exact persistence boundary. Production/consumer state was not touched.

The repair combines aggregate and retained failures in scripts/nightshift-behavior-proof.py:577, uses them for final terminal and same-prompt development retry guards at scripts/nightshift-behavior-proof.py:1125, and adds prompt binding to persisted turns at scripts/nightshift-behavior-proof.py:1228. Tests/test-behavior-multiturn.py:67 verifies both crash cases, rejects resampling before another launch, and checks legitimate development repair accounting versus final replacement requirement.

## Review conclusion

Approve the repaired diff. No remaining actionable findings identified within requested scope.

- Per-turn calls reserve/finalize existing budget units; initial admission counts all pending turns (scripts/nightshift-behavior-proof.py:1145, scripts/nightshift-behavior-proof.py:1176).
- Failure or unknown ends the conversation, and aggregate acceptance requires passing launched attempts for every recorded turn (scripts/nightshift-behavior-proof.py:901, scripts/nightshift-behavior-proof.py:1231). Normal partial evidence cannot pass the final gate (scripts/nightshift-behavior-proof.py:939).
- Actual prior completions enter replay history; oracle assertions are excluded from provider input; tools and persistence are explicitly disabled (scripts/nightshift-behavior-proof.py:1181, scripts/nightshift-behavior-proof.py:1189, scripts/nightshift-behavior-proof.py:1233).
- Per-turn current-input and final-source checks preserve existing seal/source binding (scripts/nightshift-behavior-proof.py:1209); private manifest commitment is checked by scripts/nightshift-behavior-proof.py:687.
- Scope is JSON transcript replay, not native sessions or tools, and that limitation is disclosed (docs/BEHAVIOR-PROOF.md:72).

## Verification

Original seven new offline tests passed in 12.415 seconds. Repaired eight-test suite passed independently in 19.603 seconds (tests/test-behavior-multiturn.py). Existing tests/test-behavior-proof.sh also passed independently: 25 tests in 43.467 seconds. No live model claims are made by this review.

MEX context used: .mex/ROUTER.md, .mex/context/architecture.md, .mex/context/conventions.md, .mex/context/proof-accounting.md, .mex/patterns/INDEX.md in the main nightshift-community checkout. Runtime review worktree has no .mex files. The requested legacy central memory index path does not exist.
