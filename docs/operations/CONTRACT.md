# Composable operation contract (version 1)

## Baseline and compatibility

This implementation starts at PR #61, commit `69763060dfbdac23797434f7172599116ea643f2`.
The PR is open on #60; #60 is open on #56; #56 is open on #50. Its GitHub
check is failing; inherited failures are reported separately from new regressions.
No dependency is assumed integrated. The operator checkout, installed runtime and
retained ticket records are outside this migration.

The old `scripts/nightshift-pipeline.py` dispatches stages through the factory
launcher and uses broad input signatures. Its recovery and decision modules provide
useful bounded execution, exact source hashing, raw decision validation, durable
reservation and cache semantics. The operation executor reuses those primitives,
not the recursive stage dispatch. Existing recovery commands and stored console
history, decisions and approvals remain accessible.

## Operations and artifacts

An explicit version 1 plan selects repository-relative request, specification,
scenarios, rules and accepted architecture artifacts, implementation scope, tests,
review policy, and limits. A plan is data, never authorization. The controller
binds the complete nonignored source corpus, artifact contents, worktree and common
Git directory. Rules and architecture are explicit files, including an explicit
empty-decision artifact when no architecture decisions apply. Unknown author
provenance is recorded and cannot silently become independent approval.

| Operation | Inputs | Result |
| --- | --- | --- |
| groom-spec | Request, rules, architecture | Draft specification and scenarios |
| groom-rules | Rules, architecture | Resolved immutable references |
| groom-adversarial | Draft, scenarios, resolved rules | Independent findings/disposition |
| groom | Current three suboperation results | Implementation contract |
| implement | Contract, authorized source scope, findings | Patch and actual dispatcher provenance |
| adopt | Retained draft, resolved rules, external source, explicit author provenance | External implementation checkpoint, no worker |
| verify | Contract and current source, declared tests/environment | Controller observations, nonzero test count |
| review | Current verification, contract, provenance, review policy | Independent disposition and finding resolutions |
| accept | Current review and bound operator attestation | Manual acceptance |
| publish | Current acceptance and explicit remote/branch scope | Publication receipt, never merge/deploy |

Every operation is independently assessable and runnable. Groom is an assembly
operation: it reports missing suboperations without launching them. A selected
recipe expands into an inspectable list and invokes the same operation API. A
retained draft can be imported as a draft only; no legacy model pass or process
exit imports an approval. External adoption never resets implementation or adversarial attempts. It may bind a
retained draft after Groom exhaustion as a provisional contract for Verify/Review.
It does not mark Groom passed: independent Review must resolve every retained
finding and inspect the draft, rules, scenarios, source and test oracles.

## Authority, lifecycle and migration

Assessment is read-only. Authorization records exact assessed dependencies,
operator, selected operations, per-operation limits and aggregate ceiling.
Worker recursion and grants are refused. Repeated request IDs and equivalent
successful dependencies reuse the durable result. A task lease serializes writers;
a durable pending invocation blocks redispatch even under a different request ID.
A completed checkpoint can finalize without relaunch. Each provider reservation
has an immutable ID and one terminal charge; unknown interruption retains reserved
capacity and explicitly unknown actual usage. Wall elapsed and summed provider
execution are different quantities; orchestration and deterministic tests do not
consume provider calls. No unchanged substantive failure purchases a fresh review.
Repair counts are operation-wide across authorizations, requests and sessions.

Dependency invalidation is selective. Source/environment changes affect Verify
and downstream judgments, never automatically schedule Implement. Specification,
scenario, rule or architecture changes require a new contract. Reviewer policy
changes affect Review/Accept/Publish. Every old receipt remains in history.
Migration writes a separate operation ledger, hashes historical state for audit,
and never rewrites old allowances, decisions, grants, deadlines or failures.

CLI and browser use one controller API. Existing ticket invocations with an
operation plan select its factory recipe; legacy invocations without a plan retain
legacy behavior until explicitly migrated. There is no automatic allowance grant
or silent legacy-to-new approval upgrade. The new recipe directly dispatches role
workers; it never runs the old monolithic pipeline.

## Semantic work

Independent routed AI performs drafting, implementation and substantial reviews.
Optional mapped compact obligations use the PR #61 decision engine, with exact
references, concrete evaluator identity, bounded bytes, durable cache and mandatory
risk/abstention/sampled escalation. Missing context or conflicting judgments block.
Community provider policy remains configurable. No synthetic receipt certifies
live model quality or savings.
