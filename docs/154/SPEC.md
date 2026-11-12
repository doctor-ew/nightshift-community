# 154 — Installed factory recovery certification

> Product draft from the authoritative issue. Supplemental PRD and product sign-off are absent. Source checkout behavior, installed behavior, and live certification are separate claims. Installed acceptance requires actual live evidence.

## Problem

A consumer factory run stopped before implementation after source-reference, evidence-write, receipt-type, and host authorization failures. The issue requires a recoverable installed end-to-end run, not another source-only success claim.

## Scope and constraints

Preserve the original qualified GitHub reference across child admission, preserve failed receipts and cumulative accounting, and use the current provider policy for independent review. A host approval rejection remains a host boundary. Never persist private excerpts, credentials, or transcripts in public artifacts. Existing explicit limits remain effective. Do not replace an operator installation, merge, or deploy as part of this ticket. Existing owners 66, 108, 2, 11, and 65 remain distinct workstreams in the issue request.

The issue's observed build and revision are historical evidence, not proof of the executable currently on PATH. Resolve executable, checkout, revision, install channel, and effective routed stage runtime before claiming installed acceptance. Source tests and temporary installation are labeled accordingly.

## Solution design

1. Add an inventory report for the selected executable, physical source checkout, exact revision, install channel, and effective stage route. Bind every live acceptance record to that inventory.
2. Exercise qualified GitHub intake through the actual child launcher with no seeded ticket snapshot or spec. Retain the original source reference and source snapshot as separate identities; a numeric task key must not replace the source reference before admission.
3. Validate controller-worker evidence access and declared local HTTP, database, and browser checks under the worker's scoped permissions. Preserve direct-session restrictions and host approval behavior.
4. Validate stage receipts locally before admission. A malformed numeric task identity yields a bounded original diagnostic and failed stage; it cannot become accepted evidence.
5. Carry a scoped provider authorization decision through nested dispatch and resume only where the host supports it. When host approval recurs, expose the exact rejected action and reason and a concrete resume route. Do not reframe host rejection as Nightshift review success.
6. Repair ordinary spec/review defects within retained allowances. Reuse completed evidence, require independent reviewer identity, and preserve all failed attempts. Resume tests must show no duplicate provider execution, repeated unchanged review, allowance reset, or false pass.
7. Run one isolated installed candidate from fresh ticket through Product, Adversarial, RED/GREEN Implementation, Review, Drift, and applicable QA. Retain a failed or incomplete result until actual live acceptance evidence passes. Public documentation and slides describe only the certified boundary; private records stay private.

## Files to Change

| File | Purpose | AC |
|---|---|---|
| `scripts/nightshift-factory.sh` | Installed launcher provenance and scoped worker dispatch if a gap remains | AC-1, AC-3, AC-5 |
| `scripts/nightshift-pipeline.py` | Source admission, typed receipts, recovery and evidence retention if a gap remains | AC-2, AC-4, AC-6 |
| `scripts/nightshift-preflight-check.sh` | Fresh qualified-reference admission if a gap remains | AC-2 |
| `scripts/nightshift-controller-recovery.py` | Retained repair and resume behavior if a gap remains | AC-6 |
| `scripts/nightshift-ticket-budget.py` | Preserve explicit limits and cumulative accounting if a gap remains | AC-6 |
| `scripts/nightshift-update.py` | Installed-channel diagnosis and activation if a gap remains | AC-1, AC-7 |
| `tests/test-pipeline.py` | Child admission, receipts and resume regressions | AC-2, AC-4, AC-6 |
| `tests/test-factory-preflight.sh` | Real launcher fresh-source regression | AC-2 |
| `tests/test-factory-auth.sh` | Scoped provider authorization regression | AC-5 |
| `tests/test-ticket-budget.py` | Cumulative allowance regression | AC-6 |
| `tests/test-release-inputs.py` | Installation provenance regression | AC-1 |
| `README.md` | Certified behavior and limits | AC-8 |
| `slides/saturday.md` | Certified talk claims if affected | AC-8 |
| `slides/tuesday.md` | Certified talk claims if affected | AC-8 |

The table is the maximum candidate surface, not a mandate to edit already repaired files. Additional test or documentation paths require a reviewed scope update. Installed candidate records and private transcripts stay outside public deliverables.

## Acceptance criteria

- **AC-1:** Before a live run, record actual executable, resolved checkout, exact revision, install channel, and effective stage runtime; distinguish source and active installation.
- **AC-2:** A fresh qualified GitHub reference reaches Product through the real child launcher without a seeded spec or ticket snapshot.
- **AC-3:** Validated controller workers write required evidence and execute declared local HTTP/database/browser checks within scope; direct sessions and host boundaries remain restricted.
- **AC-4:** Numeric task identity fails typed receipt admission with bounded original diagnostics; string identity and current hashes are required for acceptance.
- **AC-5:** Scoped operator authorization is retained through nested dispatch/resume where supported; recurring host rejection exposes action, reason, and recovery without bypass or leaked private payload.
- **AC-6:** Ordinary spec/review repair and interrupted resume preserve failures, independent review, completed work, counters, and allowances; no duplicate execution or false pass.
- **AC-7:** One isolated installed candidate completes fresh ticket, spec, RED/GREEN implementation, review, drift, and applicable QA with exact-revision evidence. Source-only checks and incomplete or mismatched live receipts must fail.
- **AC-8:** Public documentation and slides distinguish source fixes, temporary installation, activated runtime, and certified results without private consumer data.
- **AC-9:** If consumer work remains blocked, show its concrete eligible next action and resume path; a draft spec is never presented as completed build.

## Capability matrix and test plan

The behavioral helper reports version-1 scenarios and literal/JSON assertion operators. Its text checks cannot certify a live launcher, host approval, installed revision, or semantic documentation truth. Use ordinary command, receipt, and live-run evidence for all ACs. Each AC has a required public scenario in `docs/154/behavior-scenarios.json`; the scenario IDs match the AC suffixes. Tests must include positive and failing counterexamples. Exact installed acceptance is automated against the selected isolated candidate and its retained live receipts. No human-only attestation is required by this issue.

| AC | Automated evidence | Remaining acceptance |
|---|---|---|
| AC-1 | Inventory consistency and executable resolution | Verify actual selected installation |
| AC-2 | Fresh child launch and retained Product artifact | Confirm genuine unseeded input |
| AC-3 | Worker-scoped write and local check matrix | Confirm host scope was respected |
| AC-4 | Malformed/valid receipt fixtures | No unvalidated claim admitted |
| AC-5 | Nested/resume authorization fixtures | Host approval may still be required |
| AC-6 | Interrupted repair and allowance fixtures | Independent receipt provenance |
| AC-7 | Exact-revision six-stage live receipts and gates | Automated live receipt acceptance |
| AC-8 | Documentation claim audit | Review public/private boundary |
| AC-9 | Blocked consumer-state fixture | Concrete operator recovery |

## Model Router

**Decision:** nightshift-architect. This scope spans multiple runtime modules and a shared controller contract. Provider/model selection is resolved by configured routing at dispatch.

## Sources

- `commands/nightshift-product.md:229-247` (branch: nightshift/154, commit: 77b34f7) — existing-draft reuse and missing-draft initial authoring rules.
- `scripts/nightshift-pipeline.py:243-300` (branch: nightshift/154, commit: 77b34f7) — stage receipt parsing and validation area.
- `scripts/nightshift-pipeline.py:440-475` (branch: nightshift/154, commit: 77b34f7) — existing-draft import and Product dispatch identity.
- `scripts/nightshift-factory.sh:635-654` (branch: nightshift/154, commit: 77b34f7) — controller stage handoff and worker sandbox selection.
- `scripts/nightshift-preflight-check.sh:159-200` (branch: nightshift/154, commit: 77b34f7) — input-resolution failure and recovery.
- `scripts/nightshift-behavior-proof.py:512-630` (branch: nightshift/154, commit: 77b34f7) — public scenario schema and coverage.
- `docs/154/LIMIT-REMOVAL.md:1-17` (branch: nightshift/154, commit: 77b34f7) — local limit-removal candidate, explicitly not live certification.

The authoritative external request is [issue 154](https://github.com/doctor-ew/nightshift-community/issues/154); its observed failures and acceptance criteria are source requirements, not verified present behavior.

## Reviewed coverage repairs

The initial independent review rejected a manufactured required manual case and weak boundary coverage. The repaired scenario descriptions define concrete positive and negative receipt/test observations. The live acceptance input may be a fresh local ticket for the isolated six-stage run; qualified GitHub admission is independently exercised under AC-2. A synthetic provider fixture cannot certify AC-7. Failed reports remain retained and do not approve this revision.
