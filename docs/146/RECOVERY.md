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
