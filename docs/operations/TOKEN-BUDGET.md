# Token budget instead of byte limits

Slice 4 of the semantic-review cascade on #65. Operator rule: a request may carry
at most **64,000 tokens**, and shared state plus its longest question at most
**32,000 tokens**. No request is ever trimmed to fit.

## Where it applies

- **Jev** (`request_body`): the state plus all claim questions at most 64k; the
  state plus the longest question at most 32k (slice 2). Tokens are estimated from
  the most conservative observed bytes-per-token and measured from the provider's
  `usage` afterwards.
- **Independent LLM reviewer** (`decision-render`): one question per call, so the
  whole framing (system prompt, user prompt and schema) is held to 32k estimated
  tokens (2 bytes per token plus 300 tokens of overhead). Readiness checks the
  worst case, including a re-ask naming every role, before any authorization.

## What was removed

The 24 KiB request cap (`MAX_BYTES`, originally described as the Jev request
limit), the configurable `providers.<provider>.limits.max_input_bytes`, and the
byte checks on reviewer envelopes, reservations and readiness. `MAX_BYTES` now
names an 8 MiB safety bound for reading local artifacts and provider responses;
it is not a request limit.

## Prompt transport

The decision reviewer's user prompt, which carries the evidence, is passed to the
Claude CLI on standard input instead of as a command-line argument, so the
operating system's per-argument limit (128 KiB on Linux) no longer applies. The
role prompt and the per-packet schema remain arguments; both are small. Verified
with the Claude CLI (`claude -p` reads the prompt from stdin); the dispatcher test
stub asserts the prompt is absent from argv.

Validation: `tests/test-decision-reviewer-schema.py` (actual dispatcher, stdin),
`tests/test-reviewer-grounding.py`, `tests/test-recovery-decisions.py`,
`tests/test-recovery-independent-review.py` (over-budget evidence blocks before
any authorization).
