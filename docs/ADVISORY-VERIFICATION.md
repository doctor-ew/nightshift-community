# Advisory command verification

## Implemented and installed

Commands: help, explain, architect, dev, pm, ux-designer, architecture, ux, bmad.
Canonical contracts live in commands/nightshift-*.md; terminal dispatch lives in
scripts/nightshift-factory.sh. The Codex skill uses shared installed command
paths; scripts/nightshift-install-inventory.py includes them for every runtime.
The active runtime matches the 16 changed command, adapter, test and README files.
New shared and Claude command links resolve to that runtime.

## Verification

- tests/test-factory-cli.sh: all nine modes, multiword requests, empty help,
  Qwen and Devstral selection, Claude restricted tool arguments, push rejection,
  and no automatic manifest creation. Existing runtime/configuration cases pass.
- tests/test-factory-auth.sh: subscription/API boundaries and Claude dispatch pass.
- tests/test-factory-preflight.sh: existing factory admission invariants pass.
- tests/test-release-inputs.py: 9 pass. tests/test-setup-ux.py: 3 pass.
- ShellCheck warning-level checks and git diff --check pass.
- Inventory generation for codex, claude, local and all: shared advisory commands
  present, Claude commands included where applicable, no destination collisions.

## Live explanation probe

A real Codex subscription run read a synthetic receipt in a disposable Git
repository under the read-only sandbox. It returned the exact random evidence
marker, reported the recorded check as FAIL, and explicitly kept independent
review unavailable. The receipt remained present with its marker. This verifies
one evidence-grounded explanation, not general model quality or completed review.
Local probe artifacts: /private/tmp/nightshift-advisory-proof/run.log and
/private/tmp/nightshift-advisory-proof/docs/demo/REVIEW.md.
The first attempt stopped before execution because the fixture was not a Git
repository; the retry succeeded after initializing that disposable repository.

## Limits

Claude and local models have dispatch/argument coverage for the new commands;
no live advisory-quality evaluation was performed for them. Architecture and UX
have canonical artifact contracts and dispatch coverage, not a completed live
planning trial. The BMad bridge is optional read-only discovery/import guidance,
not vendored BMad or an automatic BMad build runner. Runtime prompts constrain
planning scope; they are not a filesystem security boundary. Invocation metrics
and the updater may write their own bookkeeping outside the agent's work.
Changes are installed locally and remain uncommitted/unpublished.

## Output modes and scoped explain follow-up

Implemented concise (new default), verbose and quiet output in
scripts/nightshift-output.py. Full text streams are retained in private user-home
log directories. Concise/quiet extract structured final answers; runtime error
results remain visible, and process exit codes/signals are preserved. The user's
local preference is verbose. Administrative commands keep their existing output.

Verification: 8 output tests pass (Codex/Claude final handling, failures, missing
answer, verbosity, private log permissions, configuration precedence, interruption).
CLI, auth, preflight, setup (3) and release/input (9) suites pass. ShellCheck and
Git diff whitespace checks pass. Ten changed implementation/test/doc files match
the installed runtime; the shared helper link resolves.

A live Codex subscription rerun used the user's docs/test-coach-brief.md with
--output concise. It described the purpose, four requirements, small scope, next
step and a single evidence-status note. The captured command events read the brief
and checked required global memory; they did not survey unrelated project proof
history. Log: /Users/doctorew/.nightshift/logs/run-67o9rnmq/stdout.log.

Usage recorded by that run: input_tokens 58066, cached_input_tokens 34816,
output_tokens 619. The original transcript's summary reported 34900 tokens under
a different reporting format; no like-for-like cost reduction is asserted.
Claude/local presentation has fixture coverage; the live follow-up used Codex.
Changes remain installed locally, uncommitted and unpublished.
