# Reviewer grounding, single re-ask and configured framing limit

An independent `yes` must cite evidence of every role in its packet (requirement,
source, assertion, observation; groom-adversarial packets have no observation).
That rule was enforced but never stated to the reviewer, whose prompt only asked
it to cite what justified the answer. A live run showed the effect: an 8-reference
packet passed because the reviewer cited everything; an 11-reference packet got a
reasonable selective `yes` that omitted the assertion role and stopped the run.

## What changed

- **Grouped answer shape.** The reviewer returns `grounding`, one list per role
  present in the packet. The packet-bound schema admits only that role's IDs in
  each list, so the obligation is visible in the structure. The controller
  flattens it to the existing evidence list, with the packet (not the chosen
  list) deciding each ID's role. Annotated IDs normalize as before; duplicates,
  unknown IDs and rebinding are still rejected. The raw report stays on disk.
- **One re-ask.** A `yes` that is otherwise valid but role-incomplete gets exactly
  one further call, by a fresh reviewer ID, whose input adds only
  `missing_roles`. It never sees the earlier answer. The re-ask reserves its own
  call from the operator's allowance and writes beside, never over, the first
  report. `no`, `abstain` and invalid answers are never re-asked. The receipt
  records the re-ask and a cache hit re-proves that the retained first answer was
  role-incomplete for exactly those roles.
- **Role prompt sent once.** It was the system prompt and also prefixed to the
  user prompt, doubling its cost against the framing limit. It is now only the
  system prompt.
- **Configured limit.** The reviewer argument limit (system prompt + user prompt
  + schema, UTF-8 bytes) is `providers.<provider>.limits.max_input_bytes` in the
  routing file in use. Absent, it is 24576, the previous constant. Valid values
  are 4096–131072; the ceiling is Linux's per-argument `MAX_ARG_STRLEN`, because
  the prompt is passed as a single argument. Readiness checks every packet
  against the worst case, including a re-ask naming every role.

- **Allowance upper bound.** A recovery plan's `limits` (the per-run allowance the
  operator approves through the assessment binding) were also capped at 600 s by a
  hardcoded check. Reviewer calls run sequentially and measured ~30 s each with
  Claude Haiku, so a 31-question plan (~17 min) could not finish in one session,
  and sessions are limited to three per ticket. The bound is now 3600 s
  (`MAX_ALLOWANCE_SECONDS`); the 64-call bound is unchanged.

The role-coverage gate itself is unchanged. Packet and envelope bounds in the
decision engine remain constants; moving them, and letting an orchestrator
propose packet shape and call counts for operator approval, is follow-up work.

Validation: synthetic tests only (`tests/test-reviewer-grounding.py` and the real
dispatcher path with a stub CLI in `tests/test-decision-reviewer-schema.py`).
Live reviewer behavior is not established by these tests.
