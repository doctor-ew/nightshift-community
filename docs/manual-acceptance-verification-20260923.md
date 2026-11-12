# Manual external acceptance

The behavioral proof helper now accepts required manual cases alongside automated
cases. Each manual case retains an owner, operator authorization, and verification
procedure. Missing AC coverage still fails. Model behavior risks cannot be
reclassified as manual. Classification review and semantic seal checks still apply.

Development admission checks the automated evidence and explicitly reports pending
manual acceptance. A manual case is not included in the passing scenario IDs.
Final completion remains blocked after the automated checks pass. Manual completion
attestation ingestion is not implemented; this change removes the preimplementation
schema mismatch, not the final acceptance obligation. The original implementation accepted authorization text without resolving its source.
That historical format now requires explicit reconciliation as described below.

The spec instructions prohibit asking for operator-owned email delivery before
implementation and prohibit manufacturing authorization or review approval.

The portal labels retained failure evidence as the latest recorded gate failure.
It explicitly warns that the receipt may belong to an earlier attempt. It does not
infer the current stop cause from file modification time. The existing conservative
blocked status remains; attempt-bound supersession is not implemented here.

## Verification

- The new regression executes an actual failing assertion, records RED, changes the
  source, records a passing assertion, admits development, and blocks final delivery
  pending manual verification. It also rejects incomplete manual contracts, optional
  manual cases, model-risk downgrades, and changes to sealed operator instructions.
  One test passed in 4.904 seconds.
- Existing behavioral proof suite: 26 tests passed in 48.770 seconds.
- Dashboard model suite: 10 tests passed. Production bundle rebuilt successfully.
- The local portal on port 8765 serves the updated historical-failure label.
- No external model process was launched for these checks. Provider stubs in the
  existing suite are synthetic. Model retries: zero. Model token usage for these
  checks: zero. Assistant-session usage is not measured by the harness.

IF-325 was stopped when checked. Its current acceptance artifact has not been
migrated, resealed or approved. Its budget has not been increased or reset, and the
ticket has not been resumed. Its completion and real email delivery are unproven.
These are local changes; publication has not been verified.

MEX context used: .mex/AGENTS.md, .mex/ROUTER.md and
.mex/context/proof-accounting.md. Source lookup was used because graph grounding
was unavailable earlier in this session. Scaffold changes remain local.

## Source-bound authorization

A manual case requires an existing recorded operator decision. The
`manual_acceptance.authorization` object contains:

| Field | Value |
| --- | --- |
| `kind` | `operator_decision` |
| `decision_sha256` | The exact decision identifier in the current task's decision record |
| `response_sha256` | SHA-256 of the canonical JSON operator response |
| `quote` | Exact nonempty text from the operator's answer or actually selected option |

The proof helper resolves the decision from the shared Git console record and
checks task identity, response provenance, digest, quotation and supersession.
An unanswered request, a worker-written file, generated scenario prose, or a
pipeline instruction cannot supply this authority. An upstream ticket quotation
without a verified authority binding is not accepted as an operator decision.
Independent classification review must still establish that the cited instruction
requires an operator-owned external check. Provenance alone does not establish that
an automated installation check needs manual acceptance.

Historical free-text authorization fails with
`manual_authorization_reconciliation_required`. Existing receipts and seals remain
on disk. Reconciliation requires either binding the actual retained instruction or
correcting a fabricated manual classification to the appropriate automated case,
then independently reviewing and resealing the changed contract through the normal
workflow. A helper must not invent an operator response to migrate an old string.
The local decision store uses the existing authenticated portal response provenance;
this does not introduce a security boundary against processes that can already
write shared Git metadata.
