# Dashboard budget continuation

Issue: https://github.com/doctor-ew/nightshift-community/issues/59

## Result

The ticket allowance panel provides an explicit Grant 10 minutes & continue
action. Existing console and budget modules own validation, launch policy and
accounting. No new workflow engine, cleanup step, or implicit budget reset is
introduced.

## Integration contract

The existing ticket budget snapshot adds `revision`, `unfinished`, and
`continuations`. `revision` is the SHA-256 of one atomic ledger snapshot;
time-derived remaining allowance is not part of its identity.

`POST /api/tickets/continue` accepts exactly the string fields `task`, `sha256`,
and `budget_revision`. Existing loopback origin and token checks apply.
`sha256` binds saved run settings. `budget_revision` binds the displayed ledger.
The console action serializes per-ticket requests, checks retained ownership,
preflight on primary and retained worker targets, and routing. The budget module
rechecks the revision under its own ledger lock before recording one grant.

Duplicate requests during an active console worker return `launched: false`.
After that worker exits, a repeated request with the earlier ledger revision is
rejected. Refreshing and explicitly clicking again is a new operator action.
The grant retains reservations and call limits and records continuation history.
Manual acceptance never becomes execution work merely because time is available.
While usable time remains, the browser action rejects a replacement allowance;
ordinary Resume uses the remaining time. This is enforced again under the ledger
lock. Historical ledgers without a deadline may receive an explicit grant.
The controller target must match the registered worktree before any grant.

## Coordination with downstream continuation repairs

Reuse the downstream implementation of retained-worktree configuration resolution
and CLI continuation admission when integrating this change. Do not replace it
with the older Community manifest resolver. The UI uses the existing console
preflight and routing entry points; it does not copy manifests, reinstall the
runtime, change provider selection, or start a separate CLI grant process.

The entry-point check includes retained-worktree collision checks and rejects
before any cleanup or grant. If a downstream controller permits additional
retained states, align admission with that controller before enabling the action.
The browser revision check must remain inside the ledger lock even if admission
is factored into a shared CLI/browser function.

## Verification

- `python3 tests/test-console-continuation.py`: seven passing tests. Real temporary
  repositories reproduce a primary manifest with no retained-worktree manifest;
  rejection preserves the ledger and starts no worker. The successful case uses
  real preflight and routing with a synthetic worker. Concurrent ledger grants
  and duplicate requests after worker exit produce one grant. Routing and manual
  acceptance blockers leave accounting unchanged.
- `python3 tests/test-ticket-budget.py`: 14 passing tests.
- `bash tests/test-console-actions.sh`: passed existing action regression checks.
- `python3 -m unittest discover -s dashboard -p test_server.py`: 11 passing tests,
  including continuation endpoint origin, token and body rejection.
- `node --test dashboard/test-model.mjs`: 13 passing tests, including continuation
  control states and protection for unspent allowances.
- `npm run build` in `dashboard`: successful; generated bundle included.

No live model calls, operator ticket continuations, budget grants, or installed
runtime changes were performed. Browser inspection could not start because the
browser plugin resolved a missing service module. Visual/manual acceptance and
live downstream continuation remain pending.
