# Adversarial admission and presentation preparation

## Problem

The retained Counsel of Ricks ticket12 stopped before implementation. An invalid
routing attempt value reached the role launcher after a retry reservation had
already been created. A separate correction to the source-repair contract did
not change the controller's Adversarial input identity, causing an unchanged
failure block despite the registered repair having changed.

## Behavior

- Validate explicit attempt, gear, risk and authentication controls before
  reservation. Duplicate or invalid controls do not launch a provider, alter a
  retry budget or overwrite a retained report.
- Bind the Adversarial input identity to `repair-checks.json` and its confined,
  bounded current/prior JSON artifacts. Generated repair receipts remain outputs.
  Product inputs are independent of this source-recheck contract.
- `--stop-before implement` runs prior gates and records a deliberate `paused`
  state before Implementation dispatch. The next action remains `implement`.
  Repeating the same command remains paused. An explicit invocation without
  that option resumes from retained evidence; it does not reset budgets.
- Saved console settings preserve the stage boundary. Resuming from the console
  cannot silently discard it. Use an explicit terminal invocation without the
  boundary when ready to start the coding demonstration.

Routing `--attempt` values1–3 describe escalation, not persistent stage receipt
numbers. A passing checker or successful provider exit never approves a gate.

## Verification

`tests/test-adversarial-admission-regressions.py` reproduces the original invalid
launch charging, missing repair dependencies and accidental implementation.
The original source fails all three regressions. Changed behavior passes the
same tests, including repeated pause, preserved planning and implementation as
the first resumed stage. Existing retry, reuse, pipeline, console and CLI suites
remain required. Test providers are synthetic; real ticket preparation is a
separate acceptance step.

## Receipt clarity follow-up plan

- [x] Distinguish missing, unsafe and oversized receipt files without reading unsafe paths.
- [x] Remove persistent stage counters from role routing examples; preserve escalation limits.
- [x] Clarify that review challenges existing facts and agreed requirements, not unimplemented planned behavior. Snapshot differences require content inspection.
- [x] Describe diagnostics as controller observations rather than worker findings; preserve retained history.
- [x] Verify diagnostic regressions, pipeline behavior and dashboard build before updating the candidate.

Acceptance: a terminated worker with no receipt is reported as missing evidence,
not a substantive rejection; unsafe paths remain rejected. Ticket12 must still
pause before Implementation, and external model review remains pending approval.

Follow-up verification: diagnostic regression suite passes 14 tests (the new
missing-file and routing-example cases failed before the repair). Dashboard
model tests pass 24 tests; dashboard production bundle builds using the existing
checkout dependencies. Python compilation and diff whitespace checks pass.
Retained diagnostic records are immutable and are not rewritten by this repair.
Live provider verification and ticket12 preparation remain pending the requested
external-source review approval. No implementation or deployment was performed.

Pipeline follow-up: all 12 synthetic pipeline tests pass with shell process
substitution permitted. The sandboxed run failed on denied `/dev/fd` access;
that failure is retained in `/tmp/ns146-pipeline-followup.log`.


Live preparation follow-up: Product attempt8 returned pass while including a
failed exploratory command in its required checks. The controller correctly
rejected it. Preserve that receipt; the next Product repair must rerun required
checks and retain exploratory failures as evidence, not passing checks. Product
and Spec routing examples also no longer use persistent gate counters.
Independent Claude static review retained locally; its console Resume concern
is intentionally constrained by the operator boundary: terminal invocation
without the option is required to resume Implementation. No independent overall
approval is claimed. During a rerun, older stage failures need a historical
label while the current ticket remains running.


## Live preparation result

Product attempt9 and Adversarial attempt5 passed with controller-validated
receipts. The controller is paused with next_action `implement` and
pause_reason `operator_stage_boundary`. There are zero Implementation attempts.
Repeating `./scripts/nightshift-demo.sh saturday --prepare` preserved the exact
completed receipt records and attempt count; no additional stage was dispatched.
The running candidate dashboard is http://127.0.0.1:8765/.
Screenshot: `/tmp/nightshift-12-ready-for-demo.png`.

For the live demonstration, run from the prepared baseline checkout:

```bash
./scripts/nightshift-demo.sh saturday
```

Omit `--prepare` to explicitly resume Implementation. Console Resume preserves
the operator boundary. Retained active usage and launch limits still apply.
No merge, deployment, feature implementation or visual acceptance is claimed.
The concise launcher currently prints “runtime returned no final answer” for
this successful deterministic pause; the persisted controller state, not that
message, establishes the accepted pause. This message remains a UX follow-up.
