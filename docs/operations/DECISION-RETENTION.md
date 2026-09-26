# Operation decision retention

## Implementation

A referenced question record must remain available. Missing pending or answered
records now block the affected operation with an explicit restoration action;
they cannot silently disappear from the current decision set.

Question identity uses normalized question text and the existing dependency basis.
Changing rationale, options, case or whitespace does not reopen a settled question.
Existing records created with the earlier task identity are reused without
rewriting their history. Changed dependencies or a different question remain
separate. No semantic equivalence is inferred for differently worded questions.
Answers remain context only; they never grant execution or allowance.

## Integration evidence

Code revision: `a38a05cc3f870ae3b6880104b4b1ffa000531ceb`.
Independent review approved controller SHA-256
`d6d06c8948363c0c40804bb40471c90e05f5b2e989d2075c8090177c6e45e3df`.
Nine adversarial, thirteen existing question and eleven manual-acceptance tests
pass. The committed browser journey includes normalized answer reuse, case-level
acceptance, bounded exhaustion and external adoption without another Implement.
Exact evidence is recorded in `DECISION-RETENTION-VALIDATION.json`.

This focused follow-up builds on the acceptance candidate. Integration of the
separate intake namespace, semantic provenance and typed verifier PRs remains a
separate tested candidate. Issue 70 remains open for full acceptance, including
cancellation/reconciliation integration under issue 71.

## Certification boundary

All fixtures use disposable repositories and synthetic providers. Token usage,
provider cache and billing remain unknown. No installed runtime, real ticket,
live allowance, merge or deployment changed.

## Repository verification checklist

- PASS: Installed names and runtime-neutral role boundaries are unchanged.
- PASS: Upstream identity remains separate from the local decision ledger.
- PASS: Independent regressions and existing decision/acceptance fixtures pass.
- UNCHANGED: No trajectory schema change.
- PASS: Claims reference source and exact receipts; graph grounding is unavailable.
- PASS: Live readiness and usage remain explicitly unverified.
