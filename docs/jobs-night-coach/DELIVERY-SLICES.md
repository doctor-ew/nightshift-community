# Jobs Night coach: epic and bounded delivery tickets

The PRD remains the full product requirement. This document proposes delivery
boundaries; it does not replace the PRD, reset the exhausted run, or claim any gate
passed. Preserve the existing ticket and its receipts as the baseline experiment.

## Dependency: evaluation capability

Before another coach repair, validate checks scoped to the proposed edit and clean
draft. Test wrong outputs with correct facts only in Works cited or Facts used.
Keep semantic entailment and arbitrary fabrication judgments with independent
review. A parser cannot establish truthfulness from word presence alone.

## Delivery sequence and coverage

| Ticket | Independently reviewable result | Original acceptance cases |
| --- | --- | --- |
| JN-1: intake and cited alignment | Pasted resume/JD to complete component inventory, overall synthesis, cited evidence and gaps; inaccessible inputs handled honestly | 1–4, 9, 11, 13, 14, 17 |
| JN-2: one evidence-to-edit cycle | One targeted question, fragmentary answer, supported proposed edit, accept/revise/skip; conservative action verbs | 5–8, 14, 15; regression of 4, 9, 11 |
| JN-3: correction and draft assembly | Accepted edits become the clean draft; rejected wording stays rejected; corrected sources update dependent claims and provenance | 10, 14, 16; regression of 5–8 |
| JN-4: portable session and release proof | Complete multi-turn session, cited companion, privacy-aware handoff, quickstart and synthetic worked example; independent final evaluation | 12 plus integrated regression of all 1–17 |

Each ticket inherits mandatory truthfulness, citation, injection resistance and
privacy requirements. Shared cases deliberately recur where a later capability
can regress them. JN-1 does not claim a complete coach; only JN-4 can establish
the first-release outcome. Provider-configurable evaluation remains shared
infrastructure, not a new product UI. Hosted UI and Word export remain out of scope.

JN-1 defines the canonical source/component contract. JN-2 extends it with proposed
edit and decision fields. JN-3 defines accepted draft and correction lineage.
JN-4 composes these contracts rather than inventing a competing format. Later
specs consume the reviewed earlier contracts. Do not rewrite every contract in
parallel. Link actual child IDs and branches here when the runs are created.

## Harness follow-through

Implemented first increment: discover supported oracle capabilities, bind literal
checks to a unique output section, require capability and repair-coverage tables,
and route unsupported checks as dependencies instead of repeated prose repairs.

Remaining work: automated validation of the capability/repair tables; executable
cross-artifact contract consistency checks; semantic grading with independent
calibration; durable finding lineage and recurrence analytics. These are not
implemented by the instruction changes alone.

Measure first-pass independent approval, recurring/new/disputed findings, wall
time, available fresh/cached/output tokens, and human interventions per approved
slice. Count failed attempts. Compare against the retained original run; do not
claim improvement from one successful example or treat missing usage as zero.

Sources: [original requirements](PRD.md#acceptance-cases),
[oracle contract](../BEHAVIOR-PROOF.md), and retained consumer findings at
`docs/spec-5e69476e580af735/design-findings-repair-{1,2,3}.json` in the Jobs Night
ticket worktree.

## Verification of the first harness increment

On 2026-09-20, the multi-turn regression suite passed 24 tests and the behavioral
proof suite passed 26 tests. The new public counterexample test accepts a fact
inside the proposed-edit section and rejects the same fact only in the supporting
facts section, outside the section, or inside ambiguous/malformed boundaries.
Capability discovery was exercised directly without launching a provider.
These are harness checks, not product approval or evidence of fewer future repairs.
