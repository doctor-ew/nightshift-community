# Testing the Nightshift talk setup

## Scope and merge boundary

These checks exercise the preserved public duration-formatter project and the isolated runtime pinned to `201970d9f8deabdf3d978297b2d035290d4f2edf`. They do not install a global runtime, reset a ticket, remove evidence, or start model generation.

On 2026-10-14, [PR #134](https://github.com/doctor-ew/nightshift-community/pull/134) was merged into `nightshift/community-integrated-20261010`. Its parent [PR #132](https://github.com/doctor-ew/nightshift-community/pull/132) remained open against `main`. Therefore, checking out `main` alone does not establish that the integration is present. The talk check uses the verified pinned installation independently of that merge boundary.

Run commands from the repository checkout. The checkout-local fixture and installation must still exist:

- `.nightshift/133-runtime/source` and `.nightshift/133-runtime/runtime`.
- `/private/tmp/nightshift-certification-133`.
- `/private/tmp/nightshift-certification-133-worktrees/spec-014c777fd4684e19`.

See [the demonstration guide](../133/DEMO.md) for the dashboard and retained fallback recording. The fixture, installation, logs and recording are local artifacts; the testing script and this guide are repository artifacts.

## 1. Check evidence and real tests without authentication

```bash
python3 scripts/nightshift-talk-check.py --check-only
```

The check verifies the pinned source revision and clean checkout, installation links, registered worktree, all six accepted stage receipt hashes and current inputs, Development and Final proof gates, and the actual duration unit tests. It runs tests with `PYTHONDONTWRITEBYTECODE=1` so existing source fingerprints remain unchanged.

Expected result: JSON with `status: "pass"`, `stages: 6`, both proof gates and unit tests reported as `pass`, `cached_repeat: false`, and `additional_provider_calls: 0`. The real test log reports three passing unit tests. The retained ticket has 26 reservations; the check requires those reservations, accepted rows and attempt history to remain unchanged.

## 2. Check the normal CLI cached repeat

```bash
python3 scripts/nightshift-talk-check.py
```

This also repeats the recorded invocation through the pinned talk wrapper. It verifies the saved policy: Codex, `gpt-6.1-sol`, subscription authentication, automatic branch, base `main`, gear 1, no push, no PR, and dashboard disabled.

An authentication-only guard permits the existing Codex and Claude subscription login-status probes. Every generation command is rejected before reaching the real provider CLI. A deliberate guard self-test must exit 75 before the repeat is attempted. Subscription login must already be available on this machine.

Expected result: `status: "pass"`, `cached_repeat: true`, unchanged accepted receipt hashes, attempts and reservations, and `additional_provider_calls: 0`. The repeat must exit zero. If inputs changed or the controller tries to start generation, the check fails; it does not erase or renew the old ticket's budget.

Each execution creates a new directory below `.nightshift/135/testing/` and prints its exact path. Inspect:

| Artifact | Purpose |
|---|---|
| `result.json` | Check outcome, pinned revision and unchanged accounting |
| `before.json`, `after.json` | Accepted rows, receipt hashes, attempts and reservations |
| `worktree.log` | Registered worktree admission |
| `development-proof.log`, `final-proof.log` | Actual proof gate results |
| `unit-tests.log` | Real unit-test output |
| `cached-repeat.log` | Normal CLI repeat output |
| `guard-self-test.jsonl` | Proof that generation is denied before execution |

A cached repeat proves evidence reuse and resume admission. It is not a fresh provider run or a new end-to-end performance measurement. Fresh acceptance needs a separate public fixture and a deliberate new run; retain this completed ticket and its original failures as the demonstrated baseline.

## 3. Run focused source regressions

These use disposable synthetic fixtures rather than subscription generation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-ticket-budget.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-handoff.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-controller-parity.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-cleanup-controller-resume.py
```

Expected result: each suite ends with `OK`. They exercise wall-clock compatibility, stage-owned and controller-assigned findings, controller parity, and completed-worktree preservation. The broader CI harness remains separate from this quick rehearsal check.

## Recorded verification

The guarded check passed on 2026-10-14 using the pinned runtime and preserved public project. Both proof gates passed; all three real unit tests passed; the cached CLI repeat exited zero. All six accepted stage rows, their receipt hashes, attempt history and 26 reservations remained unchanged. No additional provider generation calls were launched.

Local evidence: `.nightshift/135/testing/check-qvvyrmim/`. Original failure receipts and budgets remain available. This result does not verify a fresh installation, a relocated archive, or fresh provider execution.
