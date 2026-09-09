# Bootstrap fixture correction

The fixed public-corrected bootstrap case expected approval for a requirement that includes read-only access. Its scenarios exercised only active reads and expiry denial. Actual attempt 04893adbb2a54603b69afe68b30f1c15 requested repair because mutation rejection was untested. The original evaluator result remains FAIL and the call remains charged.

Independent test author review confirmed that the input was incomplete. A new external public-corrected-v2 fixture retains the two original scenarios and expected approval, adding a mutation attempt that asserts rejection and unchanged stored draft/revision. This corrects the input; it does not relabel the old output as passing or teach the prompt to ignore a valid counterexample. The fixed evaluator and private cases remain unchanged. A distinct independent review is required before executing the new version within the existing budget.

The public scenario artifact requires an explicit bot-authored amendment after that review. Preserve the original locked artifact and its review receipt in history; the replacement receives a new reviewed semantics digest. No sealed test code changes are authorized by this correction.
