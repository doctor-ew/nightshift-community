# Recovery with bounded semantic decisions

## Outcome and authority

Recovery uses deterministic controller checks for hashes, authorization, budgets,
leases, duplicates, test exit codes and stage transitions. Jev answers narrowly
scoped semantic questions. An independent reviewer handles abstentions, mandatory
risk checks and a stable 10% sample of otherwise decisive answers. A disagreement
blocks adoption. Transport, credential and malformed-response failures block without automatic fallback. A model cannot grant time, approve an operator decision or pass
manual acceptance.

The implementation is a review candidate. Synthetic verification does not certify
live model accuracy, thresholds, installed operation, latency or billing savings.
The existing optional broad Jev shadow evaluator is unchanged; this is a separate,
explicit recovery operation.

## Implemented sequence

1. `nightshift recover assess` reads the retained controller and registered
   worktree. The CLI accepts a retained task key or its exact recorded invocation
   reference, including qualified GitHub and specification references. Missing or
   ambiguous matches fail without contacting a ticket provider. It binds source, specification, scenarios, findings, test commands,
   routing, reviewer identity, decision policy and runtime assets to one assessment.
2. A committed recovery plan supplies exact requirement, source, assertion and
   observation mappings. Admission checks complete source/context coverage for
   every gate and requires explicit finding-resolution obligations. Missing plans,
   unsafe references, incomplete coverage, mutable model aliases, missing
   credentials and oversized static requests block before an allowance is created.
3. `nightshift recover authorize` requires the exact assessment hash and operator
   identity. It creates one separate allowance. Duplicate authorization returns the
   existing outcome; resume retains its original deadline and call limit. Original
   ticket limits, usage, reservations and failure receipts remain intact.
4. Tests run once in an isolated copy. The controller constructs evidence packets
   from those actual outputs and rereads source hashes. Jev receives one question
   per packet, with an actual encoded request limit of 24 KiB. Nothing is truncated
   to obtain approval. Unexpectedly large or missing test output blocks before a
   model dispatch. `assess --verify` validates actual output packets without grants
   or model calls, but does execute the declared tests.
5. Verified unchanged decisions are reused across gates within the same authorized
   session. Cache validation rechecks the packet and raw primary/reviewer artifacts
   and derives the judgment again. Pending calls do not relaunch after a crash.
6. Only verified adoption records completed implementation. Remaining review,
   drift and QA obligations run without another implementation worker. Final status
   remains pending manual acceptance. Historical failures remain visible.

The CLI and dashboard's **Review recovery evidence** action call the same
controller operation. The dashboard displays admission failures, exact requested
limits, the recorded operator and the recovery outcome. Its health response exposes
`recovery_decisions_api` so runtime compatibility can be checked explicitly.

## Recovery plan

Place the reviewed plan at `docs/<task>/recovery-plan.json` in the retained worktree
and commit it with its evidence. The parser in
`scripts/nightshift-recovery-decisions.py` is the authoritative contract. The
synthetic builder in `tests/test-recovery-decisions.py` is an executable example.

| Field | Meaning |
| --- | --- |
| `version` | Contract version, currently 1 |
| `checks` | Unique IDs and two-element `argv` arrays: `bash` or `python3`, then a repository-relative test file |
| `limits` | Explicit positive `wall_seconds`, `active_seconds`, `provider_calls`; maxima 600, 600 and 64 |
| `environment` | Optional explicit non-secret test environment; controller-owned isolation variables cannot be overridden |
| `decisions` | Bounded obligations with IDs, question kind, case/AC/finding IDs, reference spans and risk designation |

Each reference identifies its role, file/check ID and exact line range. The
controller supplies the bytes and hashes. Observation references use a declared
check ID; source, requirement and assertion references use verified relative paths.
Do not select excerpts that omit dependencies. Full-file coverage across packets
is an admission floor, not proof that separate packets capture cross-file semantics.
Split an obligation only when it is independently answerable; otherwise retain a
blocker and prepare a focused reviewable change.

`requirement_supported` decisions are reused between adoption and review.
`finding_resolved` decisions must explicitly cover every retained finding.
`scope_matches` and `oracle_valid` are distinct drift and QA obligations. These last
two kinds, and packets spanning multiple implementation files, require independent
review even when Jev is decisive. Other decisive packets are sampled; abstentions
always escalate. This conservative policy is explicit and is not a calibrated
claim of model reliability.

## Configuration and limits

The existing Jev configuration resolver reads `.nightshift-efficiency.json` and
its supported environment overrides. Enable Jev, configure the endpoint and secret
reference, and pin a deployment-verified concrete model identity. A `latest` alias
cannot authorize an evidence judgment. A returned model mismatch blocks recovery.
No secret value is written into packets, receipts or the assessment.

The independent route comes from the effective review routing. The currently
verified tool-free dispatcher for this operation is Claude subscription mode.
Other independent routes fail admission with a concrete capability limitation;
they are not silently replaced. Ordinary provider routing remains unchanged.
The reviewer receives a fresh isolated invocation, no primary answer, no tools,
and a bounded prompt plus schema. This also avoids anchoring on Jev's judgment.

The separate recovery allowance counts sequential test/reviewer execution, including
waiting for each call once. Jev and independent-review calls both consume its call
limit. This does not rewrite the original pipeline's parent-plus-child accounting.
An exhausted original ticket cannot gain time through a cache miss or new packet ID.

## Rollout work still required

- Prepare and independently inspect a complete evidence plan for the retained live
  ticket. Run its declared tests and validate actual packet sizes read-only.
- Verify a concrete Jev deployment identity and credentials without copying private
  repository contents into an availability probe.
- Evaluate a labeled public corpus with negative controls. Measure false approvals,
  false rejections, abstention/escalation rate, request bytes and time. Threshold
  changes require a new bound policy; synthetic fixtures are not calibration.
- Review both repository integrations, then explicitly install the selected private
  revision and verify dashboard runtime identity before a live recovery action.
- Present the exact current assessment, requested allowance and proposed operation
  for operator authorization. Do not reuse an approval bound to older evidence.

No real ticket continuation, installation or model call is part of these fixtures.
