# 35 — Report persistent token usage and cost per ticket

## Preamble

Task `35`; branch `nightshift/35`; commit `92b5d71`; author `codex-spec-35` (provider `codex`). The supplied fact manifest reports commit `92b5d71`; it contains no `EXTRACTED_AT` field.

## Problem

Nightshift persists immutable observation events and an atomic summary for one run, but the current schema records only input/output usage and has no collision-safe ticket identity or cross-run ticket summary (`scripts/nightshift-run-metrics.py:184-224`, `scripts/nightshift-run-metrics.py:264-315`, `scripts/nightshift-run-metrics.py:423-445`). Claude usage is read from one result envelope, while Codex JSONL usage is currently discarded (`scripts/nightshift-agent.sh:279-298`). Extend this ledger into trustworthy, restart-safe ticket accounting rather than create a separate accounting system.

## Technical Constraints

- Accounting remains observational: collection, parsing, replay, and summary-write failures do not alter provider, engineering, or gate results (`scripts/nightshift-run-metrics.py:1-24`, `scripts/nightshift-factory.sh:200-217`).
- Persist only bounded allowlisted identity, attribution, usage, cost-provenance, status, and timestamp fields; never prompts, transcripts, commands, output, credentials, ticket bodies, or local paths (`scripts/nightshift-run-metrics.py:26-33`, `docs/RUN-MEASUREMENTS.md:146-161`). Standard library only for new Python code.
- Missing usage or cost is unknown, not zero (`docs/NIGHTSHIFT-COST-POLICY.md:17-19`). Known subtotals remain visible beside completeness flags and missing/conflict counters.
- Ticket identity is the exact tuple `(source, repository, source_id)`. `external_ref` is display-only because the current GitHub adapter reduces identity to `gh-<number>` (`scripts/nightshift-ticket-source.sh:157-179`). Missing repository identity produces an explicit unattributed receipt, never a ticket-keyed receipt.
- Preserve validated stages and explicit `unknown`; the current stage allowlist is fixed and unrecognized stages are dropped (`scripts/nightshift-run-metrics.py:48-62`, `scripts/nightshift-run-metrics.py:264-287`).

## Solution Guardrails

### Identity and persistence

Extend ticket resolution to emit `repository`: for qualified GitHub references use the normalized `owner/repository`; for fetched issues derive the same value from the canonical issue URL; other adapters emit their verified source namespace or `null`. Never substitute the working-directory path. The factory and role dispatcher bind every observation to its run and ticket tuple. Batch observations bind the active ticket; shared orchestration uses `attribution: shared`, and unresolved work uses `attribution: unattributed`. Neither contributes to a ticket total.

Store immutable allowlisted receipts below `<git-common-dir>/nightshift/ticket-metrics/<ticket_key>/receipts/`, where `ticket_key` is lowercase SHA-256 of canonical UTF-8 JSON `[source,repository,source_id]`. Persist `summary.json` atomically in the same ticket directory. Each successful receipt append refreshes the summary best-effort. `ticket-report` always replays every authoritative receipt before returning and atomically refreshes an older summary, so later receipts cannot be hidden by a stale cache. Interrupted runs retain receipts already renamed into place.

Receipt identity is `(run_id, invocation_id, receipt_id, sequence)`. Exact duplicates are idempotent. Within a cumulative stream epoch, retain only the greatest sequence. Different payloads for the same complete identity are a conflict: exclude that identity from additive totals, increment `conflict_count`, and mark coverage incomplete. Retries and resumes use stable invocation/receipt identities when replaying the same provider call and new identities for new calls.

### Provider boundaries and overlap

Add proposed `scripts/nightshift-provider-usage.py` to parse captured provider JSONL without evaluating it. Claude: retain result `usage`, cache fields, `modelUsage`, and `total_cost_usd` on success and error results; in streaming mode use the latest cumulative result per reset epoch rather than summing intermediate results. Prefer `modelUsage` for inclusive whole-tree tokens when present; retain main-loop `usage` as non-additive provenance. Record `total_cost_usd`/`costUSD` as `provider_reported_estimate_usd` with provider and CLI/version provenance, never billed cost. Claude result usage excludes SDK-internal subagents, while `modelUsage` and reported estimates include them ([Claude cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), lines 83-88 and 95-140).

Codex: consume each `turn.completed` event and preserve `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, and `reasoning_output_tokens`; the event supplies no model identity, so `reported_model` stays null. `selected_model` remains routing provenance and cannot satisfy pricing identity. The verified event type is `TurnCompletedEvent { usage: Usage }` ([Codex source](https://github.com/openai/codex/blob/main/codex-rs/exec/src/exec_events.rs)); current dispatch already requests JSONL but reads only the final contract (`scripts/nightshift-agent.sh:219-227`, `scripts/nightshift-agent.sh:294-302`).

Normalize token categories as `fresh_input`, `cache_read_input`, `cache_write_input`, and `output`; retain `reasoning_output` as an output subcategory. For Claude, total is the sum of the four non-overlapping categories. For Codex, define the NEW normalized `fresh_input` category as input excluding both cache reads and cache writes: validate read plus write does not exceed provider `input_tokens`, then subtract both. This is a Nightshift partitioning requirement, not an assertion that Codex `non_cached_input()` uses this formula; Codex that function subtracts cache reads only and therefore includes cache writes. Set total to provider input plus output; cached and reasoning values are never added again. Missing or inconsistent fields increment category-missing/conflict counters instead of producing zero.

Every receipt declares `coverage_scope: self|inclusive`, `parent_invocation_id`, `included_invocation_ids`, and `child_kind: none|sdk_internal|external_dispatch`. An inclusive parent suppresses only children explicitly listed and SDK-internal children known to be included. Externally dispatched CLI children remain separate; if inclusion cannot be proven either way, expose their known usage under `nonadditive_observed`, increment `overlap_unknown_count`, and omit it from additive totals. A scope enum alone never proves disjointness.

### Cost and report contract

Capture provider-reported client estimates whenever present. Token-derived estimates are populated only from a versioned pricing table and exact `reported_model`; the pricing table and GitHub comment publisher are deferred. `actual_billed_usd` remains null without an authoritative billing receipt. Provider-reported, token-derived, and billed values are never merged.

Proposed CLI: `python3 scripts/nightshift-run-metrics.py ticket-report --project DIR --source SOURCE --repository REPOSITORY --source-id ID`. Missing/invalid arguments exit 64. Valid accounting calls remain non-gating and return JSON even when persistence is unavailable. Output schema:

```json
{
  "schema_version": 2,
  "ticket": {"source": "gh", "repository": "doctor-ew/nightshift-community", "source_id": "35"},
  "run_count": 2,
  "runs": [{"run_id": "r1", "status": "failed", "receipt_count": 2}],
  "usage": {"known_subtotal": {"fresh_input": 10, "cache_read_input": 4, "cache_write_input": 2, "output": 3, "total": 19}, "nonadditive_observed": null, "complete": false},
  "cost": {"provider_reported_estimate_usd": 0.01, "token_derived_estimate_usd": null, "actual_billed_usd": null, "complete": false, "pricing_sources": []},
  "completeness": {"missing_usage_count": 1, "missing_model_count": 1, "missing_pricing_count": 1, "unmeasured_orchestrator_count": 1, "overlap_unknown_count": 0, "conflict_count": 0, "read_error_count": 0},
  "breakdowns": {"stage": {}, "provider": {}, "reported_model": {}},
  "provenance": {"receipt_count": 3, "summary_rebuilt": true}
}
```

Breakdowns use the same additive receipt set as overall totals; each category sum must match. Unknown stages/models have explicit `unknown` buckets. Expected but unmeasured orchestrator invocations create null-usage receipts and incomplete coverage. Failed calls, retries, repairs, resumes, and child calls are retained regardless of engineering status.

## Guardrails

All upstream ACs apply. Preserve subscription auth, independent gates, existing CLI compatibility, private allowlisted receipts, and non-fatal accounting. Implement the identity, provider normalization, overlap, persistence, and report semantics in Solution Guardrails.

Controller integration clarification (Codex, before independent review): the following new interfaces were collision-checked against the existing metrics and dispatcher sources. `python3 scripts/nightshift-run-metrics.py ingest --run-dir DIR --receipt-file FILE` accepts one normalized JSON receipt, sanitizes it, links it to the existing run event ledger and ticket receipt store, and refreshes the atomic report best-effort. No separate accounting-only run registry replaces existing run contexts. A receipt contains `schema_version:2`, `ticket` (the three identity fields or null), `attribution:ticket|shared|unattributed`, `run_id`, `invocation_id`, `receipt_id`, nonnegative `sequence`, `stream_epoch`, `provider`, `selected_model`, `reported_model`, `stage`, `status`, `role` (or `orchestrator`), `coverage_scope`, `parent_invocation_id`, `included_invocation_ids`, `child_kind`, `usage` (the normalized categories plus optional reasoning output and total), and `cost` (the three distinct USD fields and `pricing_sources`). Missing optional observations stay null; missing identity is unattributed. Only typed allowlisted fields survive persistence. Ingestion cannot accept a different run ID than its validated context.

The proposed provider helper CLI is `python3 scripts/nightshift-provider-usage.py --provider PROVIDER --input FILE`; it emits normalized allowlisted provider observations as a JSON array for the owning boundary to bind to its trusted run/invocation/ticket identity. It never derives trusted attribution or invocation identity from model text. It must support Claude's existing single result JSON object as well as JSONL, and Codex JSONL. Runtime/source version provenance accompanies reported client estimates when available; absent version stays unknown. Billing and token-derived estimates remain unknown without their respective authoritative inputs.

Receipt ingestion and report failures stay observational and return structured unavailable/incomplete output. A report with no measured category uses null, not an empty sum of zero. A run without measured orchestrator usage increments `unmeasured_orchestrator_count`. Resolve shared/unattributed work explicitly in run summaries without allocating it to tickets.

## Files to Change

| File | Action | Change | AC |
|---|---|---|---|
| `scripts/nightshift-run-metrics.py` | MODIFY | Versioned receipt schema, replay/dedup/overlap rules, atomic ticket summary, and `ticket-report`. | AC1-AC7 |
| `scripts/nightshift-provider-usage.py` | CREATE | Strict Claude/Codex JSONL adapters and normalized receipt output. | AC3-AC5, AC8 |
| `scripts/nightshift-agent.sh` | MODIFY | Capture success/error JSONL, emit child receipts and actual reported usage/model/cost provenance. | AC1, AC4, AC5, AC8 |
| `scripts/nightshift-factory.sh` | MODIFY | Bind run/ticket identity; capture orchestrator receipts; mark shared/unattributed batch overhead. | AC1, AC5, AC8 |
| `scripts/nightshift-ticket-source.sh` | MODIFY | Return collision-safe repository identity where verified. | AC1 |
| `docs/RUN-MEASUREMENTS.md` | MODIFY | Document receipts, totals, completeness, persistence, and read CLI. | AC3-AC7 |
| `docs/NIGHTSHIFT-COST-POLICY.md` | MODIFY | Distinguish client estimate, token-derived estimate, and actual billing. | AC4 |
| `tests/test-ticket-accounting.sh` | CREATE/TEST | Focused baseline-failing and final deterministic coverage for cases C35-1 through C35-8. | AC1-AC8 |
| `tests/test-run-metrics.sh` | MODIFY/TEST | Provider fixtures for cache fields, reported estimate, cumulative results, errors, and privacy. | AC3-AC5, AC8 |

## Acceptance Criteria

- **AC1.** Two runs for one ticket produce one correct cumulative report, including failed attempts, without mixing another ticket's usage.
- **AC2.** Replaying receipts, rebuilding summaries, or resuming a run does not duplicate usage or cost.
- **AC3.** Parent/child overlap and cached-token categories have explicit semantics and regression coverage.
- **AC4.** Missing usage, missing model identity, and missing pricing produce explicit incomplete reports, never fabricated zero cost or a misleading complete total.
- **AC5.** Available orchestrator usage is included; an unmeasured orchestrator visibly makes coverage incomplete.
- **AC6.** A documented machine-readable read operation returns persisted ticket totals and provenance after restart. Interrupted runs retain already-recorded usage.
- **AC7.** Stage metadata is retained where known, with overall totals consistent with any breakdown.
- **AC8.** Tests cover ticket isolation, aggregation, replay/resume, pricing provenance, partial coverage, and accounting I/O failures; relevant existing runtime/provider tests remain green.

## Risks

- Provider formats can vary by installed version; unsupported or missing fields must degrade to explicit incompleteness.
- Parent/child relationships may be unavailable; conservative exclusion avoids double billing but leaves incomplete totals.
- Concurrent receipt writers require write-once rename and locked atomic summary replacement; receipts remain authoritative.

## Dependencies

Python standard library, existing provider JSONL, Git common-directory persistence, and the controller-verified Claude/Codex contracts above. No pricing service or upstream writeback is required.

## Test Plan

Authoritative RED/final command: `bash tests/test-ticket-accounting.sh`. Its baseline RED must fail relevant accounting assertions, not import or syntax. Cases map C35-1→AC1 through C35-8→AC8. Run `bash tests/test-run-metrics.sh`, `bash tests/test-agent-dispatch.sh`, and `bash tests/test-factory-auth.sh` as relevant regressions; preserve existing assertions while extending only the declared metrics fixture. C35-8 requires independent safety design challenge before sealing; all cases use deterministic final assertions. Tests must not be weakened to accept incomplete capture.

## Open Questions

- The supplied extractor has no `EXTRACTED_AT`; the controller must add the actual extraction timestamp if its ledger has one.
- A token-derived pricing table and idempotent GitHub comment are explicitly deferred; provider-reported client estimates are not deferred.

## Model Router

**Decision:** nightshift-architect

## Sources

- `scripts/nightshift-run-metrics.py:1-66` (branch: nightshift/35, commit: 92b5d71) — observational contract and current enums.
- `scripts/nightshift-run-metrics.py:145-224` (branch: nightshift/35, commit: 92b5d71) — Git persistence, atomic writes, and run initialization.
- `scripts/nightshift-run-metrics.py:264-349` (branch: nightshift/35, commit: 92b5d71) — current observation receipt and replay fields.
- `scripts/nightshift-run-metrics.py:390-445` (branch: nightshift/35, commit: 92b5d71) — current deduplication, aggregation, and atomic summary.
- `scripts/nightshift-agent.sh:31-47` (branch: nightshift/35, commit: 92b5d71) — role observation boundary and stage attribution.
- `scripts/nightshift-agent.sh:207-302` (branch: nightshift/35, commit: 92b5d71) — provider commands and current usage parsing.
- `scripts/nightshift-factory.sh:200-217` (branch: nightshift/35, commit: 92b5d71) — run context propagation and non-gating summary.
- `scripts/nightshift-factory.sh:459-512` (branch: nightshift/35, commit: 92b5d71) — orchestrator provider boundary and observations.
- `scripts/nightshift-ticket-source.sh:35-100` (branch: nightshift/35, commit: 92b5d71) — identity derivation contract.
- `scripts/nightshift-ticket-source.sh:157-179` (branch: nightshift/35, commit: 92b5d71) — current GitHub identity loss and fetched URL.
- `docs/RUN-MEASUREMENTS.md:68-128` (branch: nightshift/35, commit: 92b5d71) — persisted run summary and current token semantics.
- `docs/RUN-MEASUREMENTS.md:130-168` (branch: nightshift/35, commit: 92b5d71) — stage, privacy, and non-fatal metrics behavior.
- `docs/NIGHTSHIFT-COST-POLICY.md:1-19` (branch: nightshift/35, commit: 92b5d71) — authentication and unknown-not-zero policy.
- `tests/test-run-metrics.sh:1-84` (branch: nightshift/35, commit: 92b5d71) — existing provider fixture and regression baseline.
- `docs/BEHAVIOR-PROOF.md:1-48` (branch: nightshift/35, commit: 92b5d71) — public scenario schema, classifications, risks, and review fields.
- `docs/PROJECT-CONTEXT.md:1-44` (branch: nightshift/35, commit: 92b5d71) — project identity and authoritative test-command selection rules.
