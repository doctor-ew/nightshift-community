# Workshop v2 verification — 2026-09-13

Task: `workshop-cf7288cdfde0d6f4`; brief: `test-coach-brief-v2.md`.
Verdict: runtime recovery succeeded; independent artifact inspection found a behavioral false pass.
This audit does not modify the original run or its complete status.

## Integrity and accounting

- State records complete; 18 invocations, including the original failed final review and one successful retry; no prompt repairs.
- All 42 `verified_files` hashes match. The prompt hash and approved spec hash match separately.
- The artifact is 20 lines and includes the four requested coaching requirements.
- All 18 raw runtime receipts reconcile exactly to state totals.
- Active duration: 330.522926 seconds (about 5 minutes 31 seconds), excluding approval/operator wait.
- Fresh input: 1,178 tokens; cache writes: 49,431; cache reads: 18,801; output: 27,022. Total including cache: 96,432 tokens.
- Reported cost: $0.4740602, including failed review and retry. Subscription usage estimate, not an API invoice. Separate diagnostic reviewer probes are not part of this run total.

## Findings

1. **Unsourced alternative claims passed.** EVALUATION-0 case-7 names Zoom, Discord, Stripe and Devpost as existing alternatives to proposed features, without supplying source URLs. The brief requires a source URL for any competitor or alternative claim; prompt lines 5–7 extend that obligation to the coach itself. Asking which tools the student has researched does not supply sources for the coach's own claims. The case-specific grader passes this response, and the final overall reviewer raises no issue.
2. **Final reviewer cites evidence absent from a response.** `code-review-0.json` says case-4 and case-8 preserve a synthetic scenario/placeholder URL. Case-8 is a request for harsh feedback; its recorded response does not discuss a synthetic scenario or placeholder URL. This is an unsupported assertion in the evidence audit. Case-4 and case-6 do contain relevant synthetic reasoning.
3. **Case-7 grading overstates observed behavior.** Its pass explanation describes negotiation tied to experiments. The response asks about the audience, advocates three features, and argues for pre-set success criteria, but does not yet ask for an experiment for each feature. A later conversational turn could do that; these single-turn observations do not demonstrate it.

Positive evidence: case-2 now treats a supplied URL as an unverified citation pointer; case-4 preserves synthetic labeling; case-6 refuses an unsourced invented competitor; case-5 challenges a universal audience claim. These are improvements, not justification for accepting unrelated missed requirements.

## Consequence

The recorded 8/8 result is not sufficient to endorse this prompt as fully verified.
Follow-up work should check every response against all applicable requirements,
require reviewer evidence references to match the actual case text, and distinguish
completed behavior from a promise to address it in later turns. Do not reset or
rewrite the original receipts to make the machine status agree with this audit.

## Evidence location

Original project: `/Users/doctorew/shuttlebay/_ATL_/GSU/Hack-Her-Thon-runthrough-test-202609131533`.
Worktree: the adjacent `Hack-Her-Thon-runthrough-test-202609131533-worktrees/workshop-cf7288cdfde0d6f4` directory.
State: project `.git/nightshift-workshop/workshop-cf7288cdfde0d6f4.json`.
Artifact: worktree `prompts/workshop-agent.md`.
Spec and evaluation: worktree `docs/workshop-cf7288cdfde0d6f4/{SPEC.md,CASES.json,EVALUATION-0.json,code-review-0.json,RUN.json}`.
Accounting: that directory's `calls/*.stdout.json`, selecting the recorded receipt for each invocation; the retry is `code-review-0.retry-1.stdout.json`.
