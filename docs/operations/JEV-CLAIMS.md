# Jev claims, tiered thresholds and token budgets

Slice 2 of the semantic-review cascade on #65.

## Narrow claims instead of one compound question

Version 2 recovery plans produce version 3 decision packets carrying `claims`:
statements taken verbatim from the obligations, never paraphrased. Each case
contributes its `then` clause, its `forbidden` clause ("The implementation does
not do the following: …"), and each `expected` or `prohibited` item; each retained
finding contributes one claim. A packet with no such text falls back to its
question.

The Jev request keeps the packet as shared `state` (without the claim list) and
asks one `noul` question per claim, prefixed by the question kind (for example
"The cited assertions and observed results genuinely and non-vacuously test
this: …") and followed by the evidence rule. All claims are answered in one call.

Verdict per packet: every claim at or above the tier's passing bar is `yes`; any
claim at or below the failing bar is `no`; otherwise the packet escalates to the
independent reviewer. Version 1/2 packets keep the single `supported` question.

## Thresholds by consequence (policy version 2)

| Tier | Kinds | Pass at | Fail at |
|---|---|---|---|
| acceptance | requirement_supported, finding_resolved, oracle_valid (and unknown kinds) | ≥ 0.90 | ≤ 0.10 |
| supporting | scope_matches | ≥ 0.80 | ≤ 0.20 |

Risk is expressed through the tier, so a confident answer on a high-risk packet
is not re-asked; uncertain answers escalate, and the shadow sample (10%) keeps
feeding calibration against the independent reviewer. Receipts retain the policy
and every claim score; cached receipts re-derive the verdict from the raw Jev
answer. Receipts written under the version 1 policy stay valid and keep its rules. The default policy follows the packet: claim packets (version 3, from version 2
plans) use policy version 2; version 1 and 2 packets, including handoff reviews,
keep the version 1 policy unchanged (`default_policy`).

## Token budget instead of a byte cap

Per the operator's rule, a Jev request may carry at most 64,000 tokens, and the
shared state plus its longest question at most 32,000. Before the call, tokens
are estimated from the most conservative bytes-per-token observed on the route
(from previous receipts' `usage.input_tokens`), seeded at 2.0 bytes per token
plus 300 tokens of overhead. After the call, the receipt records Jev's measured
`usage` and whether it exceeded the budget. The packet byte limit used by the
independent reviewer path is unchanged here and is removed in a later slice.

## Verified against the live service

One synthetic two-claim request built by `request_body` was accepted by
`https://api.typesafe.ai/v1/systemone` with model `jev-1.13.0`: 0.21 s, 1,181
input tokens for 2,456 bytes (about 2.8 bytes per token after overhead, so the
seed is conservative).

Validation: `tests/test-decision-engine.py` (26) and the Jev path of
`tests/test-deterministic-evidence.py` (controller run with a synthetic transport).
