# Optional bounded semantic handoffs

## Contract

The existing `reviewer_policy.semantic_plan` remains optional. A null value uses
ordinary independent review without a Jev dependency. Version 1 obligation plans
remain Review-only. Version 2 adds an explicit `stage` on each obligation:
`groom-adversarial` or `review`.

Preparation supports `preparation_supported`, `requirement_package` and
`oracle_valid`. Its references contain requirements, proposed source/contracts
and assertions. They do not represent execution. Review supports
`requirement_supported`, `scope_matches`, `oracle_valid`, `finding_resolved` and
`integration_supported`, and additionally requires verified execution observations.
Version 2 findings include the exact retained text and its digest.

The read-only `semantic-map` action generates a complete candidate mapping from
current controller artifacts. It writes no files, creates no grant and invokes no
provider. CLI example for an existing operation plan:

```sh
python3 scripts/nightshift-operations.py semantic-map demo groom-adversarial --project /path/to/disposable-project
```

The same action is available through the shared operation API. The candidate must
be persisted as the explicitly selected semantic plan before authorization. This
initial mapping deliberately includes complete relevant files; it makes no claim
that matching IDs establishes semantic coverage. Independent Groom or Review
receives and evaluates the exact mapped obligations before Jev runs.

Inline package artifacts are covered by the complete graph manifest and its hash.
No nonexistent caller file or executed observation is invented. Missing evidence,
oversized packets, invalid spans and unsupported profiles block explicitly.
References are bounded before allocating span coverage. Required context is never
silently truncated or removed by an evaluator.

## Authority and reuse

Deterministic code selects allowed operations, verifies hashes, reserves calls and
execution time, enforces deadlines and validates transitions. The existing
configurable evaluator transport and independent reviewer routing remain in use.
Jev evaluates only the bounded semantic question. It cannot authorize commands,
choose allowances, schedule packages, accept manual cases or publish.

The stage, exact packet, evaluator configuration, policy and reviewer route bind
durable decision receipts. Source, requirements, observations, mappings or policy
changes invalidate affected evidence. Required independent review remains even
when Jev is positive. Abstention, high risk and deterministic sampling use the
existing independently budgeted escalation; unavailable evaluators do not trigger
an unrecorded alternative. Positive child judgments never replace parent tests
and integration review.

## Reference and evaluation boundary

The user-supplied [Jev engineering study](https://drive.google.com/file/d/17h982xvsL3E7b80iGmOCfKp9qTOW9ohv/view)
informs explicit typed state and purpose-built context. It identifies itself as
an independent synthesis. It is not an API specification or calibration study.
Its illustrative routing prices and token shares are not Nightshift measurements.

Synthetic fixtures test positive, negative, abstaining and conflicting judgments,
missing/oversized evidence, stale references, disabled policy, independently
rejected mappings and receipt reuse. Stub scores exercise control flow; they do
not measure Jev accuracy, false approvals, false rejections or confidence
calibration. Provider tokens, provider-cache usage, billing and savings remain
unmeasured. No real evaluator, installed runtime or ticket is activated.

A separate live evaluation proposal must pin candidate revision, endpoint/model,
credential source, labeled public fixture digest, call/time ceilings and independent
review route. It must compare outcomes against independent fixture labels and
report per-kind false approvals/rejections, abstentions, escalation, latency and
measured usage separately. No live execution is authorized by this document.

## Synthetic integration receipt

Runtime revision `eb1540ed57ede7827e5f3424d6e194db287d4b75` passes ten
handoff cases (15.352 seconds), eleven independently authored regressions (4.993
seconds) and twenty existing decision-engine cases (0.058 seconds). The integrated
operation wrapper subsequently passed all88tests across12suites, including
launcher, isolated installation, restart, repair and byte-preservation regressions.
The runtime remained `eb1540e`; `db2eb0b` added documentation-only evidence.

The positive preparation fixture uses eight calls: two ordinary independent
operations, three evaluator calls and three independent escalations. It reuses
three decision receipts and adds zero calls on replay. Exact request bodies total
24,597 bytes, with zero unknown reservations; measured synthetic execution is
0.004264709998096805 seconds. Per-request bytes and source hashes are retained in
`SEMANTIC-HANDOFFS-VALIDATION.json`. This latency is a local stub measurement,
not provider latency. Tokens, provider cache, billing and live quality remain
unknown. An earlier undercount of escalation envelopes was reproduced by an
independent failing regression and corrected before this revision.
