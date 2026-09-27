# Engineering operations

Operations consume versioned artifacts and retain their own evidence and allowance.
The factory executes an explicitly authorized recipe through the same controller.
An operation never launches missing upstream work implicitly.

## Prepare an isolated repository

Keep the source checkout used by an installed runtime unchanged during evaluation.
Use a separate worktree and place a plan at `docs/<task>/operations.json`.
The plan schema is `contracts/nightshift-operation-plan.schema.json`; the executable
synthetic example is `tests/test-operations.py` (`fixture`). It names five explicit
input files, source paths the implementation may change, declared test scripts,
a test environment, reviewer policy, bounded allowances and an optional publication
target. Rules and architecture are explicit versioned inputs. Existing accepted
architecture records remain binding and are checked independently.

The scenario artifact is a version 1 object with nonempty `cases`. Each case has
exactly `id`, `requirement` and Boolean `manual`. Required manual cases remain
pending until a current operator attestation. An existing legacy scenario document
must be adapted explicitly; migration never upgrades an old approval automatically.

Test commands are two-element arrays: `python3` or `bash`, followed by a relative
repository test script. Verification executes them in a disposable source copy and
retains raw output. A failing, empty or all-skipped test run cannot pass. The current
adapter recognizes unittest and pytest summaries. Independent review must inspect
actual assertions, coverage and test oracles; a process exit alone is insufficient.

## CLI

These commands work in fish as well as POSIX shells. Replace uppercase values with
values returned by assessment; no shell-specific environment assignment is needed.

```text
nightshift ops view TASK
nightshift ops assess TASK groom-spec
nightshift ops authorize TASK groom-spec --binding HASH --operator OPERATOR --request REQUEST
nightshift ops run TASK groom-spec --grant GRANT --request INVOCATION
nightshift ops authorize TASK --recipe factory --binding HASH --operator OPERATOR --request REQUEST
nightshift ops chain TASK --grant GRANT
```

`--project DIR` selects the repository. Authorize returns the durable grant ID;
duplicate authorization may return an existing ID. Always use that returned ID.
Individual operations are `groom-spec`, `groom-rules`, `groom-adversarial`, `groom`,
`implement`, `adopt`, `verify`, `review`, `accept` and `publish`. The `groom` recipe
runs its three independent suboperations and assembles the contract. The `factory`
recipe stops after Review, leaving human acceptance pending. The `external` recipe
adopts explicitly attributed source and runs Verify and Review without Implement.
A selected recipe stops on its first blocker or failure; targeted author repair is
separately callable under its recorded allowance. It never buys an unchanged review.

`nightshift ops migrate TASK --operator OPERATOR --request REQUEST` imports a
retained draft as draft evidence only. It records hashes of legacy pipeline and
budget ledgers without rewriting them. Existing history, chat, stored answers and
recovery actions remain available through their original APIs. A legacy factory
invocation with an operation plan uses the authorized factory recipe. Without a
plan, the legacy path remains unchanged; migration is explicit.

## Adoption, acceptance and publication

Authorize `adopt` with `--attestation` containing the assessed `binding`, external
`identity`, and `provider` (`human`, `claude`, `codex` or `local`). An optional `model`
is recorded; absent model provenance remains unknown. Adoption can bind a retained draft and resolved rules after classification
exhaustion, preserving the failed Groom receipts. This records author provenance
and a provisional contract, not correctness or a passing Groom judgment. Verify and independent Review are still required.

Authorize `accept` with an attestation containing the exact assessed `binding` and
`accepted: true`, after completing the declared manual cases. Authorize `publish`
separately with the assessed binding and exact plan `publication` object. Publication
requires a clean, already reviewed commit on the named non-default branch. It
pushes that commit to the explicit remote/branch and records the resulting head.
It never merges, deploys, creates a commit or publishes private controller evidence.

## Dashboard and recovery

The Engineering operations panel assesses a task key, shows each operation's state,
blocker, next action, findings, evidence and allowance, and lets the operator select
one operation or an explicit recipe. Authorization, execution and restart use the
same controller APIs as the CLI. Existing ticket history and recovery controls are
retained. HTTP success is not a successful gate.

After an interruption, use the same grant and invocation. A completed checkpoint
finalizes without another provider call. A controller-recorded provider completion
can be reconciled with its original charge. An unknown unfinished invocation remains
blocked, with reserved capacity explicitly unknown; it cannot silently relaunch.
Changes to inputs or policy require reassessment. Old receipts remain in history.

## Compact semantic obligations

An optional `reviewer_policy.semantic_plan` identifies a version 1 obligation file.
`tests/test-operation-decisions.py` constructs a synthetic example. Each obligation
maps requirements/findings to exact requirement, source, assertion and observation
spans. Full context coverage is required, oversized packets fail without truncation,
and scenario IDs must be covered. Finding IDs are hashes of retained finding text.
The supported kinds and packet rules are enforced by the existing PR #61 decision
engine. Scope, oracle, high-risk, abstention and sampled cases receive fresh
independent review. Mandatory substantial code review remains required.

Configuration uses the existing Community routing and Jev configuration resolvers.
Routes and evaluator settings are bound to authorization and evidence. No provider
fallback or downstream-specific configuration is installed by these operations.

See `CONTRACT.md` for migration design and `ROLLOUT.md` for the separate live proposal.

## Repeatable browser verification

From `dashboard`, run `npm ci --ignore-scripts`, `npx playwright install chromium`,
and `npm run test:browser`. The runner creates a temporary Git repository, home and
synthetic provider executables, starts the real dashboard and clicks its controls
through a fresh headless Chromium profile. It also compares results with the CLI.
Screenshots and a JSON receipt are written to ignored `test-output/browser` and
retained by CI as the `nightshift-operation-browser` artifact for 30 days.
`NIGHTSHIFT_BROWSER_ARTIFACTS` selects another report directory. No real ticket or
provider is used. The CI workflow runs this test before the offline evaluation
harness. For a shared browser cache, set `PLAYWRIGHT_SKIP_BROWSER_GC=1` before
installing to preserve other cached test-browser versions.

Cancellation and retained-evidence recovery: [operation cancellation and reconciliation](CANCELLATION-RECONCILIATION.md).

Supported typed Verify profiles and legacy compatibility: [typed verification integration](TYPED-VERIFICATION-INTEGRATION.md).
