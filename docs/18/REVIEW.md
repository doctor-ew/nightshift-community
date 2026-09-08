# Review: provider-neutral core

Verdict: APPROVE. No unresolved blocking findings.

Independent cross-provider source reviews used Claude/sonnet against the Codex-authored
implementation. Reports: review.out.json and review-repair.out.json. These are static
reviews; the reviewer explicitly did not claim test execution. Their evidence gap at
review time is resolved by the subsequently retained receipts directory.

The first spec report was rejected for conflating proposed and existing behavior.
Its original output and budget category remain retained. The corrected source review
mapped absent proposed capabilities to NET_NEW. No counter was reset.

Independent runtime testing found that the initial test-role wording failed to read
both convention sources. The scoped prompt repair makes discovery/read-all an explicit
pre-execution gate. Fresh unchanged cases then blocked conflicting commands under both
Claude and Codex; legacy commands retained exact arguments. Codex's original fixture
required a receipt write unavailable in the preserved read-only sandbox. The independent
tester corrected that harness to emit evidence to stdout, and validated actual CLI
command events, exact arguments, exit zero, one test, source lines and immutable inputs.
The original failed cases are preserved in receipts/attempt1 and receipts/attempt2.
Final Codex execution and hashes are in receipts/readonly/validation.json.

Offline verification: all 34 suites passed across the full run and two focused reruns.
The new suite has 15 passing methods with no skips. The two focused reruns correct only
logical-vs-physical temporary path setup; existing auth/state assertions are unchanged.
Shell syntax and git diff whitespace checks pass. CI remains a merge prerequisite.
