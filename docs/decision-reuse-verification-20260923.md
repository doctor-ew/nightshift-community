# Decision reuse and worktree routing

Repeated decision requests now return an existing answer rather than creating
another pending occurrence. Legacy questions match normalized text; callers can
supply a stable decision_key across rewording. Reopening requires the latest
answered decision hash in supersedes and a nonempty reopen_reason. Reasons are
recorded, not semantically validated. Unrelated legacy wording can still evade
matching; the engineering instructions now require stable keys.

Ticket worktrees without a local manifest recover routing from the primary
checkout's manifest. Explicit routing overrides retain precedence. This prevents
workers from silently reverting to bundled role models after setup on the primary
checkout. No decision reuse result approves a review or behavioral gate.

Validation: 11 decision tests, 10 chat tests, 4 routing tests and 11 portal HTTP
tests passed. The decision regression failed before the implementation. Whitespace
checks passed. The routing fixture uses a real linked Git worktree. Provider calls
were not used for this verification.

Local IF-325 configuration and its saved resume settings now select Claude-only;
the work profile restores Haiku, Sonnet 5 and Opus 5.5 role tiers. Sonnet effort-tier
selection is not implemented by this change. No active factory was restarted or
budget increased. An already-running process retains its invocation settings.

Still unresolved: distinguishing operator-owned manual email acceptance from
mandatory automated pre-implementation proof. This change does not weaken a gate
or claim delivery. The separate live Claude chat failure also remains unresolved.

MEX context used: .mex/ROUTER.md and earlier session context. The router update is
local source documentation, not a published change. Naming, upstream ticket
identity, runtime-neutral roles and trajectory schemas are unchanged; fixtures
cover decision and routing boundaries. Graph grounding remains unavailable.
