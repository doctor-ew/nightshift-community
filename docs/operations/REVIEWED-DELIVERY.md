# Reviewed delivery

## Scope

The delivery controller prepares an exact reviewed commit, publishes its branch,
opens a pull request and observes integration CI. Independent actions and endpoint
composition use the same controller through the launcher and browser. Acceptance
must be current before delivery authorization. Deployment is outside this contract.
Merge requires a separate action and an enabled profile; it is never part of the
endpoint composition.

## Profile

Create `docs/<task>/delivery.json` beside the operation plan. Version 1 requires
exactly these fields:

| Field | Contract |
| --- | --- |
| `version` | Integer `1` |
| `remote` | Existing Git remote name |
| `remote_url` | Exact single effective push destination; URL rewrites cannot change it |
| `repository` | GitHub repository in owner/name form |
| `branch` | Current topic branch; cannot be main, master or the base |
| `base` | Existing remote base branch |
| `files` | All operation scope paths, optionally request/spec/scenarios inputs; unique explicit paths |
| `checks` | Required check identities, each with `name` and positive integer `app_id` |
| `endpoint` | `branch`, `pr` or `ci`; CI requires nonempty check identities |
| `merge_policy` | `disabled` or `protected-squash` |
| `commit` | Exact `message`, `author_name` and `author_email` |

Private controller directories, environment files, and the active operation and
delivery configuration files cannot be included even when listed in scope. The commit uses a separate index, reviewed raw bytes and executable
modes. Git clean filters cannot transform accepted bytes. Unrelated staged changes
and operator files remain intact. A retained commit receipt is required for branch
publication. Unpublished history must descend from the exact remote base and contain
only receipt-backed reviewed commits. Unknown operator commits are preserved and
block publication, including unrelated files added and later deleted in history.
Declared test-script bytes and modes must match the reviewed commit. Changed tests
therefore need explicit source scope and publication; an unpublished test change
cannot certify delivery. History traversal is bounded to 1,000 commits and checks
active cancellation/deadline before each commit.

## Shared actions

`scripts/nightshift-delivery.py` implements assessment, authorization, execution,
reconciliation and retained CI repair. `scripts/nightshift-factory.sh` exposes it
as `nightshift delivery`. The browser uses the same operation API and shows the
push destination, repository, topic/base branches, exact revisions, intended file
hashes, trusted check identities and endpoint before authorization.

`deliver` composes `commit`, `branch`, optional `pr` and optional `ci` in that order.
Each child retains its own action receipt and inherits the parent cancellation and
deadline. A failed or unknown step stops dependent steps. Standalone actions remain
available. A new request cannot silently expand the configured endpoint.
Without a bound repair grant, endpoint composition stops at failed or unknown CI.
At `deliver` authorization, optional `attestation.repair_grant` selects an existing
bounded factory grant with the same operator and current source/policy. Its immutable
identity, remaining deadline and additive parent cancellation are bound before any
delivery effect. The browser offers existing matching factory allowances with
remaining call ceilings and expiration; it does not require reconstructing a grant
ID from controller state. Supplying a grant only at execution is rejected.

On an eligible CI failure, composition persists a handoff, refreshes current CI
evidence and uses the same repair registration and supervisor. Passing, queued or
unknown current checks cannot trigger repair from an old failure. Successful repair
returns `needs_acceptance`; it never accepts, commits or republishes repaired source
automatically. Replay reuses the retained handoff without another Implement. An
explicit current external adoption requests Verify/Review when missing, then fresh
acceptance, without renewing the old factory authority or repeating Implement.

Delivery windows are keyed by profile and accepted file hashes/modes. Re-review or
an operator change cannot renew the same source window. Changed source with fresh
current acceptance can receive a separately explicit new delivery authorization;
the original factory deadline and task-wide CI repair ceiling remain unchanged.

| Receipt status | Meaning |
| --- | --- |
| `commit_prepared` | Exact reviewed tree has a retained local commit receipt |
| `branch_published` | Exact commit was observed at the configured push destination |
| `pr_open` | One owned pull request matches source repository, branch, base and head |
| `ci_passed` | Required trusted checks passed on a candidate with exact head/base parents |
| `ci_failed` | A required current check completed with a substantive failure |
| `ci_unknown` | Missing, stale, queued, skipped, cancelled or otherwise nonpassing evidence |
| `integrated` | The host confirms the separately authorized merge |

Branch publication compares the expected old remote revision and permits only an
already validated fast-forward. A force-moved source or base invalidates authority.
PR ownership uses a deterministic marker and repository identity; ambiguous or
foreign-fork matches block. CI admission checks names and application IDs, exact
merge candidate and both parents. An incomplete paginated check response blocks.
Host output larger than 2,000,000 bytes is retained but blocks evidence admission;
it is not truncated into a successful receipt. A closed unmerged PR cannot pass. Protected merge additionally requires strict
branch checks and the exact source revision; host acceptance without confirmed
integration remains pending.

## Repair and reconciliation

Completed CI failures with retained diagnostics can register an existing bounded
factory authorization. Registration does not launch a provider. Explicit retained
repair resumes Implement, Verify and independent Review through the operation
supervisor. Repairs invalidate previous judgments and require fresh acceptance
before further delivery. Timeout and action-required conclusions cannot trigger
implementation. Missing diagnostics block repair rather than inventing a cause.

Canonical source/base/check failure identity ignores rerun IDs, order and unrelated
checks. Repeated registration retains the same repair and adds parent cancellation
restrictions. Parent and child wall intervals overlap and must not be summed as
independent execution time. Delivery transport calls are separate from provider
invocations; missing token/cache/billing measurements remain unknown. At most three CI repairs are registered per task, across commits and
operators; existing call limits and deadlines still apply. External implementation
uses adoption, Verify and Review without another Implement call.

Intent is persisted before effects. Unknown remote effects require observation
before another request can act. Reconciliation may observe after cancellation or
expiry, but cannot dispatch a remote mutation. Replayed success rechecks current
source and remote identity. Evidence and unknown usage remain retained.

## Certification boundary

This contract is an implementation candidate. Synthetic test results, exact tested
revisions and request accounting are recorded separately. They do not certify a
live provider, Git host policy, semantic accuracy or billing savings. Community
provider routing remains configurable. Deployment and shared-service identity are
optional downstream profiles and are not prerequisites for local branch/PR delivery.
