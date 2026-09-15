# Autonomous architect regression

## Problem and change

An autonomous implementation dispatch returned no patch because the architect role unconditionally required interactive plan approval. The factory now exports its execution mode, the dispatcher supplies that mode in provider prompts, and the architect follows autonomous or supervised policy consistently. Read-only authoring returns a patch for controller integration; sandbox permissions and engineering gates are preserved.

## Validation

- Dispatcher suite: 106 assertions passed, including Codex and Claude autonomous/supervised prompt propagation, factory-mode propagation, read-only sandbox preservation, and existing copy/symlink installed dispatch checks.
- Factory authentication suite: passed, including execution-mode propagation to the provider process and existing subscription, credentials, resume, and exit-status coverage.
- Live subscription call through the repaired architect dispatcher: Codex gpt-5.6-sol returned SUCCESS, a plan, and a one-line patch without requesting approval. The worker left the fixture source unchanged. The controller checked and applied the returned patch, then the fixture test passed. See live-result.json.
- Shell syntax and git diff whitespace checks passed.

## Evidence limits

The live check used a synthetic admitted one-file task and the existing test-only behavioral-proof fixture. Its synthetic review attestations are fixture setup, not independent review of this fix. This proves one real autonomous proposal handoff; it does not establish reliability for a large task or resolve model availability, dispatch timeouts, or repeated review latency. Issue 35 remains the separate end-to-end accounting shakedown.
