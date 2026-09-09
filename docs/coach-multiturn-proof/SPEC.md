# Bounded multi-turn text proof

Add explicit `claude-subscription-multiturn-text-v1` admission for tool-free
conversation replay. Preserve the single-turn profile unchanged.

Acceptance: sealed prototype inputs contain 1–16 ordered turns, each with
positive and prohibited completion assertions; reject malformed or unbounded
turns. Carry actual prior completions into subsequent inputs, isolate cases,
and never accept a case until all turns and final case assertions pass.
Charge each provider launch against existing budgets; reserve before launch,
retain per-turn integrity hashes and accounting, stop on failure/unknown.
Preserve independent challenge, heldout, input freshness and source gates.
No live-provider execution, tool support, budget reset or auth fallback.

Files: scripts/nightshift-behavior-proof.py, tests/test-behavior-multiturn.py,
docs/BEHAVIOR-PROOF.md. Offline regression tests first, then existing proof suite.
