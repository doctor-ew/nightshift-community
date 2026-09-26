# Semantic evidence provenance

## Implementation

Semantic handoffs previously accepted arbitrary file-role labels and combined
context coverage across separate obligations. Independent escalation also turned
a generic review approval into an attestation over every reference.

The controller now derives permitted roles from inspected operation inputs and
check scripts. Each obligation must contain the complete required context and
exact scenario IDs. Independent escalation must explicitly return assessed
`evidence:`, `requirement:` and `finding:` identifiers in its coverage. Derived
receipts contain only evidence identifiers returned by that worker. Missing or
malformed coverage blocks acceptance; raw output and charged calls are retained.

These deterministic checks establish provenance and completeness, not semantic
truth. Jev continues to evaluate bounded semantic connections; independent AI
owns substantial reasoning and required review. Explicit `semantic_plan: null`
retains the optional profile. A selected semantic plan with an unavailable or
disabled evaluator remains blocked rather than silently bypassing review.

## Integration evidence

Code revision: `c8a9429cee389a661cb26e1abbca97a61f96007e`.
Independent review approved bridge SHA-256
`0ac0cc27ac9c8b56e39d8aa1ca926ba9a6882669e1412c134291d8ae88c6acd7`.
Thirteen adversarial provenance tests pass. Existing handoff (10), legacy (3),
review (11) and cache (6) tests pass. The committed positive fixture records eight
synthetic calls, three semantic receipt cache hits and zero calls on replay.
Per-request bytes and usage are in `SEMANTIC-PROVENANCE-VALIDATION.json`.

## Certification boundary

No real evaluator/provider was called. Recorded elapsed seconds measure synthetic
fixture execution, not inference latency. Token usage, provider cache and billed
cost are unknown. The change builds on the integrated intake/semantic candidate;
no installed runtime, live ticket, allowance, merge or deployment changed. Issue
68 remains open for full integrated acceptance and endpoint certification.

## Repository verification checklist

- PASS: Existing installed names and runtime-neutral roles are preserved.
- PASS: Upstream ticket identity remains separate from the local ledger.
- PASS: Existing and independent fixtures cover provenance and accounting.
- UNCHANGED: No trajectory evidence-schema change.
- PASS: Claims have source/test receipts; graph grounding is unavailable.
- PASS: Live semantic accuracy, usage and readiness remain explicitly unverified.
