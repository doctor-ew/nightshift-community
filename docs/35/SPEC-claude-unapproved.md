# 35 — Report persistent token usage and cost per ticket

## Preamble

- Task key: `35` (source: `gh`, external ref: `gh-35`, per `scripts/nightshift-ticket-source.sh:74-90` derive-id classification).
- Branch: `nightshift/35`. Commit: `92b5d71`.
- Prior spec-writer attempts on this task: attempt 1 (`FAIL` — permission denial writing `docs/35/*`, all research retained), attempt 2 (this document — read-only handoff per controller instruction; the controller performs the actual file writes).
- Code-fact extraction (`nightshift-code-fact-extractor`) ran and returned `SUCCESS` at `2026-09-15T14:57:43.956072+00:00` against this same commit; every citation below was independently re-verified against the worktree at `92b5d71` in this session (not merely carried over from that manifest), and no claim in this body rests on an extractor claim marked anything other than `VERIFIED`.

## Problem

Nightshift records per-run token usage in `<git-common-dir>/nightshift/runs/<run_id>/summary.json` (`scripts/nightshift-run-metrics.py:423-441`), but nothing aggregates those runs by upstream ticket. A ticket worked across `/nightshift-product`, `/nightshift-implement`, retries, and repairs produces one `run_id` per factory invocation (`scripts/nightshift-factory.sh:204-207`), each with its own directory; there is no persisted mapping from a ticket's external reference (e.g. `gh-35`) to the set of `run_id`s that belong to it, no code that aggregates their `usage` totals, and no documented read operation a UI could call to get a ticket's cumulative totals. Cost is not recorded at all today — only `input_tokens`/`output_tokens` are captured (`scripts/nightshift-run-metrics.py:282-285`), and only for the Claude provider (`scripts/nightshift-agent.sh:279-293`); Codex and local runs report token usage as `null` by design (`scripts/nightshift-agent.sh:294-296`, `docs/RUN-MEASUREMENTS.md:176-178`).

## Technical Constraints

- Metrics remain strictly observational: every existing non-fatal-failure guarantee in `scripts/nightshift-run-metrics.py` (fixed stderr warning, exit 0, no gating — module docstring `scripts/nightshift-run-metrics.py:6-9`, and repeated per-command in `cmd_init`/`_summary`/`cmd_event`) must hold for every new subcommand and field added here. Ticket accounting failures must never change `nightshift-agent.sh`'s `status`, `nightshift-factory.sh`'s `terminal_status`, or any gate outcome.
- Only allowlisted, typed fields may be written by `nightshift-run-metrics.py`; no prompts, transcripts, ticket titles/bodies, file paths, full commands, environment dumps, or credential values (module docstring `scripts/nightshift-run-metrics.py:26-33`; restated at `docs/RUN-MEASUREMENTS.md:148-156`). New fields extend this allowlist; they do not create a side channel around it.
- `docs/NIGHTSHIFT-COST-POLICY.md:17-19`: "Missing usage or cost information means unknown, not zero." Every new aggregate must preserve this — a partial sum is never presented as a complete total, and an absent orchestrator/provider measurement makes coverage explicitly incomplete rather than silently omitted.
- Existing dedup already exists and must not be re-described as absent: `_summary` (`scripts/nightshift-run-metrics.py:391-394`) deduplicates observation events by `invocation_id` and repair events by `(task, key, old, new)` **within one run**. `invocation_id` is only unique inside a single run: `nightshift-agent.sh:14` mints `agent-$$-$(date)-$RANDOM` per dispatch, and `nightshift-factory.sh:471,511` both emit the constant `factory-$NIGHTSHIFT_RUN_ID` for a run's own direct-provider launch (mutually exclusive call sites — the interrupt handler at `nightshift-factory.sh:469-473` vs. normal completion at `nightshift-factory.sh:509-513` — so at most one such event exists per run). A cross-run ticket aggregator must therefore dedup on `(run_id, invocation_id)`, never on `invocation_id` alone.
- `_load_context` (`scripts/nightshift-run-metrics.py:227-244`) rejects any run directory whose `context.json` `run_id` disagrees with the ambient `NIGHTSHIFT_RUN_ID` the caller has exported (`scripts/nightshift-factory.sh:207`). A cross-run ticket reader iterates many run directories that were never the "current" run for the process reading them, so it needs its own read path that validates ownership/symlink safety (reusing `_owned_nonsymlink_dir`, `scripts/nightshift-run-metrics.py:161-174`) without that single-run identity check.
- No Git common directory means no persisted run receipt at all (`scripts/nightshift-run-metrics.py:190-194`); a ticket report over such a project can only ever be empty/unavailable, never fabricated.
- Per `https://code.claude.com/docs/en/agent-sdk/cost-tracking` (fetched by the controller, not independently re-fetched in this session): `total_cost_usd`/`costUSD` are client-side estimates, not billing; a single result envelope's `usage` excludes subagent usage while `modelUsage`/`total_cost_usd` include it. This repo's only observed Claude envelope shape is the result-level one captured at `scripts/nightshift-agent.sh:279-293` (`usage.input_tokens`/`usage.output_tokens` on the top-level `.result`/`.structured_output` envelope, confirmed live by the fixture at `tests/test-run-metrics.sh:24` and the production extraction code). No `modelUsage`/`total_cost_usd`/cache-token fields have been observed at this provider boundary in this codebase; their existence in some `claude -p` invocation is plausible per that doc but **unverified in this repo** and is not implemented here (see Open Questions).
- Codex's `turn.completed` usage shape (`input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`) was reported to this session by the controller from `openai/codex` at blob `f6ad902779bee05ab0fb9b9cc6a2bca59d52c136`, not independently fetched here, and is **not** the event stream this repo's Codex dispatch actually parses today: `nightshift-agent.sh:219-227,297-298` runs `codex exec --json --output-last-message "$TMP/final"` and reads only the final structured-output file, never the `--json` event stream, so no `turn.completed` event is read anywhere in this codebase today. Implementing a Codex/local usage adapter is out of scope for this ticket (see Open Questions); Codex/local usage stays `null`, unchanged.
- No pricing table ships in this delivery. Any dollar figure recorded is the provider's own reported cost where a provider reports one; today no adapter in this repo captures a provider-reported dollar figure at all (`scripts/nightshift-agent.sh` extracts only `usage.input_tokens`/`usage.output_tokens`), so every persisted report's cost fields are `null` with an explicit `cost_status: "unknown"` until a future ticket adds a verified provider cost field or a versioned pricing table.
- Subscription-only auth is unchanged (`docs/NIGHTSHIFT-COST-POLICY.md:1-9`); nothing here reads or writes API-billing credentials.
- GitHub comment publication (brief "Should have") is explicitly deferred; no file in this ticket's scope posts to an upstream tracker.

## Solution Design

Extend the existing per-run private ledger (`<git-common-dir>/nightshift/runs/<run_id>/`) with a persistent, ticket-keyed index and a read-only cross-run aggregator, rather than building a parallel accounting system:

1. **Thread ticket identity into observations at the point they are already emitted.** `nightshift-factory.sh` already resolves a ticket's `source`/`source_id`/`external_ref` for preflight admission via `nightshift-ticket-source.sh --derive-id` (`scripts/nightshift-preflight-check.sh:147-151`, documented at `docs/RUN-MEASUREMENTS.md:90-95`), but never captures that identity itself or passes it onward. `nightshift-factory.sh` will call `--derive-id` a second time, independently, for its own metrics purposes (same no-network-fetch, identity-only mode already in production), record `{source, source_id, external_ref}` into the run's `context.json` at `init` time, export them as new environment variables for role dispatch, and pass them on every `nightshift-run-metrics.py event` call it already makes (`scripts/nightshift-factory.sh:204,470-472,510-512`). `nightshift-agent.sh`'s `emit_observation` (`scripts/nightshift-agent.sh:31-48`) picks up the same exported variables and passes them through unchanged. A run with no resolvable ticket identity (e.g. `--branch none`, ad hoc local run) simply records `external_ref: null` — unknown, never a guessed or default value.
2. **Distinguish orchestrator usage from role usage explicitly.** `nightshift-factory.sh`'s own direct-provider observation (`scripts/nightshift-factory.sh:470-472,510-512`) and `nightshift-agent.sh`'s per-role-dispatch observation (`scripts/nightshift-agent.sh:31-48`) are not duplicates of each other — the factory-level event is the orchestrator's own call when it runs a provider directly (advisory/architecture/ux paths, `scripts/nightshift-factory.sh:480-502`); the agent-level event is a role worker's own call. Both can occur in the same `run_id` and must both be summed, not deduplicated against each other, per the Anthropic guidance that orchestrator-level totals legitimately include internal subagent usage. Add a new allowlisted `usage_scope` field (`"orchestrator"` | `"role"`) to the observation record so a reader can report each subtotal and can flag orchestrator coverage as incomplete when `nightshift-factory.sh`'s own direct-provider call records no usage (it captures none today — no `--input-tokens`/`--output-tokens` flag is passed at `scripts/nightshift-factory.sh:470-472,510-512` — satisfying acceptance criterion 5 by making that gap explicit rather than silent).
3. **Persist a per-ticket run index, not a recomputed scan of every run directory.** On `init`, once a run's `external_ref` is known, write one file per run under `<git-common-dir>/nightshift/tickets/<external_ref>/runs/<run_id>.json` (new, proposed path — no existing file or directory under `nightshift/tickets/` exists in this repo; checked via repo-wide grep, no collision). Each file is that run's own receipt (its `run_id`/`external_ref` only; usage still lives solely in that run's own `summary.json`), written once with the same atomic-temp-file-then-rename discipline already used for `summary.json` (`scripts/nightshift-run-metrics.py:177-181`), avoiding any partial-write or concurrent-append race entirely.
4. **Add one new read-only aggregator, `scripts/nightshift-ticket-report.py` (new, proposed — no existing file of this name; checked via repo-wide grep, no collision).** Given `--project DIR --external-ref REF`, it:
   - Resolves the Git common directory the same way `scripts/nightshift-run-metrics.py:145-158` does.
   - Lists `nightshift/tickets/<REF>/runs/*.json` (rejecting symlinks/non-owned entries with the same `_owned_nonsymlink_dir` predicate, `scripts/nightshift-run-metrics.py:161-174`) to get every `run_id` ever recorded for that ticket, including runs whose factory process crashed before writing a final `summary.json` (interrupted/failed runs are included by design — the index entry is written at `init`, before any provider call, so a retry or a resumed run that produced a fresh `run_id` is still counted, and a run that never finished is visibly present with only partial/`null` usage rather than silently absent).
   - For each `run_id`, reads that run's own `summary.json` if present (complete, atomically-written) or, if absent (process died before any `summary` call), independently replays that run's `events/` directory using the same `_read_events`/dedup logic as `_summary` (`scripts/nightshift-run-metrics.py:318-349,390-394`) so an interrupted run's already-recorded usage is not lost (satisfies acceptance criterion 6, "Interrupted runs retain already-recorded usage").
   - Deduplicates across the whole ticket on `(run_id, invocation_id)` — never `invocation_id` alone (see Technical Constraints) — so replaying receipts, rebuilding a stale `summary.json`, or resuming a run under the same `run_id` never double-counts (acceptance criterion 2).
   - Sums `usage.input_tokens`/`usage.output_tokens` separately per `usage_scope` (`"role"` vs `"orchestrator"`) and reports a combined total only when both scopes that actually occurred are complete; an entirely-missing orchestrator scope (no orchestrator-scoped observation exists at all in the ticket's runs) is reported as `orchestrator_usage: {"observed": false, ...}`, distinct from an observed-but-incomplete scope, so "no orchestrator instrumentation happened" and "instrumentation happened but some values are null" are never conflated (acceptance criterion 5).
   - Reports per-`stage`/`provider`/`model` breakdown from the same observations (`stage`/`provider`/`model` are already recorded per observation, `scripts/nightshift-run-metrics.py:274-286`), with overall totals equal to the sum of the breakdown (acceptance criterion 7) — computed from one pass over the same deduplicated observation list.
   - Reports `repair_count` as the ticket-wide sum of each run's own already-deduplicated `repair_count`, `null` (not `0`) if any contributing run's `repair_count` is `null` (unchanged semantics from `scripts/nightshift-run-metrics.py:398-403`).
   - Emits `cost`: always `{"reported_usd": null, "estimated_usd": null, "billed_usd": null, "cost_status": "unknown", "pricing_source": null}` in this delivery (see Technical Constraints; no adapter captures a dollar figure today). The shape exists so a future ticket can populate it without a schema change; it is not itself a cost feature.
   - Prints one JSON object to stdout; writes nothing (the "documented machine-readable read operation," acceptance criterion 6). It never mutates any run directory, ticket index, or summary file.
   - Is defensive exactly like `nightshift-run-metrics.py`'s existing commands: any I/O or parse failure on one run's data is recorded as that run's `contributing_runs[].status: "read_error"` (an accounting I/O failure surfaced in the report's own completeness fields, acceptance criterion 8) rather than aborting the whole report or raising a nonzero exit that could be mistaken for a gate signal.
5. **Documentation only, no new behavior.** `docs/RUN-MEASUREMENTS.md` gains a new section describing the ticket index, the `usage_scope` field, and `nightshift-ticket-report.py`'s output shape. `docs/NIGHTSHIFT-COST-POLICY.md` gains one paragraph distinguishing reported/estimated/billed cost and stating that this delivery reports none of them as a nonzero number.
6. **GitHub comment publication, stage-attribution UI, and any pricing table are out of scope for this ticket** (brief: "Should have," "must not displace required accounting correctness"). Nothing here prevents a follow-on ticket from consuming `nightshift-ticket-report.py`'s JSON to post or render either.

## Files to Change

| File | Change | Why |
|---|---|---|
| `scripts/nightshift-run-metrics.py` | Add allowlisted `source`, `source_id`, `external_ref`, `usage_scope` fields to `cmd_event`'s `observation` record (extends the dict built at lines 271-287) and thread them through `_read_events`/`_summary` (lines 318-349, 423-441) into `summary.json`. Add a new run-index write helper (`nightshift/tickets/<external_ref>/runs/<run_id>.json`) invoked from `cmd_init` once identity is known (lines 184-224). | AC1, AC3, AC5, AC7 |
| `scripts/nightshift-ticket-report.py` (new) | New read-only cross-run aggregator per Solution Design item 4. | AC1, AC2, AC4, AC5, AC6, AC7, AC8 |
| `scripts/nightshift-factory.sh` | Call `nightshift-ticket-source.sh --derive-id` for metrics purposes near the existing `init` call (line 204); export the resolved identity; pass `--source/--source-id/--external-ref` and `--usage-scope orchestrator` on both existing observation `event` calls (lines 470-472, 510-512). | AC1, AC3, AC5 |
| `scripts/nightshift-agent.sh` | Read the new exported ticket-identity variables in `emit_observation` (lines 31-48) and pass `--source/--source-id/--external-ref --usage-scope role` on its existing `nightshift-run-metrics.py event` call (lines 43-47). | AC1, AC3, AC5 |
| `docs/RUN-MEASUREMENTS.md` | Add a "Per-ticket accounting" section documenting the ticket index, `usage_scope`, and `nightshift-ticket-report.py`'s JSON contract, after the existing "Dispatcher observations" material (after line 220). | AC6, AC7 |
| `docs/NIGHTSHIFT-COST-POLICY.md` | Add a paragraph distinguishing reported/estimated/billed cost and stating this delivery's cost fields are always `unknown` (after line 19). | AC4 |
| `tests/test-ticket-metrics.sh` (new) | Deterministic CLI-level regression coverage per Test Plan below. | AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8 |

## Interface Contract (for independent TDD)

`nightshift-ticket-report.py --project DIR --external-ref REF` prints exactly this shape to stdout and exits `0` whenever `DIR` is readable and resolves to a Git repository (exit `64` for a missing/invalid `--project`/`--external-ref`; exit `0` with an empty-but-valid report, never a nonzero exit, for "ticket has zero recorded runs" or "no Git common directory" — absence of data is not an argument error):

```json
{
  "schema_version": 1,
  "external_ref": "gh-35",
  "run_count": 2,
  "contributing_runs": [
    {"run_id": "…", "status": "summarized", "terminal_status": "provider_exited_0"},
    {"run_id": "…", "status": "replayed_from_events", "terminal_status": null}
  ],
  "usage": {
    "role": {"input_tokens": 1000, "output_tokens": 300, "complete": true},
    "orchestrator": {"observed": false, "input_tokens": null, "output_tokens": null, "complete": false}
  },
  "repair_count": 1,
  "breakdown": {
    "by_stage": {"implement": {"input_tokens": 1000, "output_tokens": 300}},
    "by_provider": {"claude": {"input_tokens": 1000, "output_tokens": 300}},
    "by_model": {"sonnet": {"input_tokens": 1000, "output_tokens": 300}}
  },
  "cost": {"reported_usd": null, "estimated_usd": null, "billed_usd": null, "cost_status": "unknown", "pricing_source": null}
}
```

`contributing_runs[].status` is one of `summarized` (read `summary.json` directly), `replayed_from_events` (no `summary.json`; reconstructed from `events/`), or `read_error` (this run's data could not be read; it contributes nothing and marks `usage.role.complete`/`usage.orchestrator.complete` `false` for the ticket). No status value ever contributes a fabricated zero.

## Acceptance Criteria

1. GIVEN two separate factory runs recorded for `external_ref` `gh-35`, one of them terminating with `terminal_status: provider_exited_nonzero`, WHEN `nightshift-ticket-report.py --external-ref gh-35` runs THEN both runs appear in `contributing_runs`, their `usage.role` totals are summed, and a third run recorded under a different `external_ref` contributes nothing to this report.
2. GIVEN a run's `summary.json` is regenerated (an idempotent `summary` re-run) or a `run_id` is reused across a resume, WHEN the ticket report is regenerated THEN no observation is counted twice, because dedup keys on `(run_id, invocation_id)`.
3. GIVEN one run contains both an `orchestrator`-scoped and a `role`-scoped observation, WHEN the ticket report runs THEN both subtotals appear separately under `usage.role`/`usage.orchestrator` and are not deduplicated against each other.
4. GIVEN no adapter in this delivery captures a provider-reported dollar cost, WHEN any ticket report runs THEN `cost.cost_status` is always `"unknown"` and no `*_usd` field is a fabricated number.
5. GIVEN a run whose orchestrator-scoped observation was never emitted (the common case today), WHEN the ticket report runs THEN `usage.orchestrator.observed` is `false` and `usage.orchestrator.complete` is `false`.
6. GIVEN `nightshift-ticket-report.py` is invoked after the process restarts and GIVEN a run that was interrupted before writing `summary.json`, WHEN the report runs THEN it returns the persisted ticket totals including that interrupted run's already-recorded observation events (replayed from `events/`).
7. GIVEN observations across two stages/providers/models for one ticket, WHEN the report runs THEN `breakdown.by_stage`/`by_provider`/`by_model` sum to the same totals as `usage.role`/`usage.orchestrator`.
8. Tests cover: ticket isolation (AC1), replay/resume dedup (AC2), parent/child scope separation (AC3), missing-cost provenance (AC4), incomplete-orchestrator coverage (AC5), restart/interrupted-run reconstruction (AC6), breakdown-consistency (AC7), and one accounting I/O failure that does not change any other run's contribution or raise a nonzero exit (AC8); existing `tests/test-run-metrics.sh` and `tests/test-factory-auth.sh` remain green unmodified.

## Guardrails

- Accounting is observational only: no file in this ticket's scope may cause `nightshift-agent.sh`'s `status`, `nightshift-factory.sh`'s `terminal_status`, or any `nightshift-behavior-proof.py gate` outcome to change based on accounting success or failure.
- Only the fields named in this spec's Files to Change are added to the allowlist; no prompt, transcript, file path, full command, environment dump, or credential value is ever accepted by `nightshift-run-metrics.py` or `nightshift-ticket-report.py`.
- `cost.cost_status` is `"unknown"` in every code path shipped by this ticket; no hardcoded or derived dollar figure may be introduced without a versioned `pricing_source` and a verified provider-reported field, neither of which exists in this repo today.
- `nightshift-ticket-report.py` is read-only: it must not write to any run directory, ticket index entry, or `summary.json`.
- A missing/ambiguous ticket identity is recorded as `external_ref: null`, never a guessed or default ticket key; such runs are excluded from every ticket report and are not silently merged into another ticket's totals.

## Risks

- **Scope creep into pricing.** Mitigated by shipping `cost.cost_status: "unknown"` unconditionally rather than a partial pricing table.
- **Double-counting across `usage_scope`.** Mitigated by keeping `role` and `orchestrator` as separate, never-merged subtotals (Solution Design item 2).
- **Silent identity loss.** A ticket whose `external_ref` fails to derive must not be misattributed; mitigated by `external_ref: null` propagating through unmerged.
- **Codex/local usage adapter temptation.** Explicitly out of scope; the controller-relayed `turn.completed` field names are unverified in this repo and this repo's Codex dispatch does not read the `--json` event stream today.

## Dependencies

- None outside this repository. No new third-party package; `nightshift-ticket-report.py` uses only the Python standard library, matching `nightshift-run-metrics.py`.

## Test Plan

Deterministic CLI-level regression tests, added in `tests/test-ticket-metrics.sh`, following the fixture pattern already used by `tests/test-run-metrics.sh` (temp Git project, stub `claude`/`codex` binaries, real script execution — no mocking of the code under test):

- `test-ticket-metrics.sh::AC1-ticket-isolation` — run the factory fixture twice for the same `external_ref`, once for a different one; assert the ticket report sums exactly the first two runs' usage and excludes the third.
- `test-ticket-metrics.sh::AC2-replay-dedup` — call `nightshift-run-metrics.py summary` twice for the same `run_id`; assert the ticket report's total is unchanged between the two calls.
- `test-ticket-metrics.sh::AC3-scope-separation` — record one `orchestrator`-scoped and one `role`-scoped observation in the same run directory; assert both appear under separate keys and neither is dropped or summed together.
- `test-ticket-metrics.sh::AC4-cost-unknown` — assert `cost.cost_status == "unknown"` and every `*_usd` field is `null` on every fixture run.
- `test-ticket-metrics.sh::AC5-orchestrator-incomplete` — a run with only a `role`-scoped observation; assert `usage.orchestrator.observed == false` and `usage.orchestrator.complete == false`.
- `test-ticket-metrics.sh::AC6-restart-interrupted` — write a run's `events/` directory directly (simulating a crash before any `summary` call, never writing `summary.json`), invoke the report as a fresh process; assert the recorded observation's usage appears via `replayed_from_events`.
- `test-ticket-metrics.sh::AC7-breakdown-consistency` — two observations with different `stage`/`provider`/`model`; assert breakdown sums equal `usage.role` totals.
- `test-ticket-metrics.sh::AC8-io-failure-non-gating` — make one run's directory unreadable while a sibling run for the same ticket stays intact; assert the report still exits `0`, still reports the sibling run's usage, and marks the unreadable run `read_error`.

Existing `tests/test-run-metrics.sh` and `tests/test-factory-auth.sh` are expected to remain green unmodified — new fields are additive to `summary.json` and `nightshift-run-metrics.py event`'s existing accepted flags.

Behavioral case IDs `AC1`–`AC8` in `docs/35/behavior-scenarios.json` map one-to-one to the acceptance criteria above; every required case there is classified `deterministic` except `AC-safety-1`, which is `deterministic` with risk `safety_sensitive` (the "accounting never gates, never captures disallowed content" guarantee) and therefore requires independent design challenge before development proceeds, per `docs/BEHAVIOR-PROOF.md`.

## Open Questions

- Does `claude -p --output-format json` ever emit `modelUsage`, `total_cost_usd`, or cache-token fields at the envelope this repo's dispatcher actually parses (`scripts/nightshift-agent.sh:279-293`)? Not observed in this repo; needs direct in-repo verification before any cache-token or cost field can be added for Claude.
- Does Codex's `--json` event stream (not the `--output-last-message` final file this repo currently reads) expose a `turn.completed` event with structured `usage`, and does this project's pinned Codex CLI version emit it? The field names were relayed to this session from an external source lookup performed by the controller (`openai/codex` blob `f6ad902779bee05ab0fb9b9cc6a2bca59d52c136`), not independently verified in this session, and are not present anywhere in this codebase today. Deferred to a follow-on ticket.
- Should the per-ticket run index be pruned/rotated over time, or is unbounded retention acceptable for this pilot? Not addressed by the brief; deferred.
- GitHub comment publication (brief "Should have") is deferred entirely; no interface or file path for it is proposed here.

## Model Router

**Decision:** nightshift-architect

(7 files across `scripts/`, `docs/`, and `tests/` — three top-level modules — exceeds the ≥3-files/≥2-modules threshold, and item 2's `usage_scope`/parent-child accounting semantics is a shared-contract change to the `summary.json`/observation-event shape multiple scripts read and write.)

## Sources

- `scripts/nightshift-run-metrics.py:1-493` (branch: nightshift/35, commit: 92b5d71) — full read; module docstring (6-33), constants (46-73), `_atomic_write` (177-181), `cmd_init` (184-224), `_load_context` (227-244), `cmd_event` (247-315), `_read_events` (318-349), `cmd_summary`/`_summary` (352-447) confirm the exact observation/repair schema, dedup behavior, and non-fatal-failure guarantees relied on above.
- `scripts/nightshift-agent.sh:1-307` (branch: nightshift/35, commit: 92b5d71) — full read; `role_stage` (21-30), `emit_observation` (31-48), `INVOCATION_ID` (14), role dispatch gating (138-149), routing/provider selection (161-227), Claude envelope usage extraction (279-293), Codex/local final-file-only parsing with no structured-usage capture (294-298).
- `scripts/nightshift-factory.sh` lines 59,160,168,185 (raw `REF`), 204-207 (metrics init/export), 245-250 (`nightshift-preflight-check.sh --ref` call), 394 (prose policy line, not a code invocation), 440-525 (provider launch and both existing observation `event` calls at 469-473 and 508-513) (branch: nightshift/35, commit: 92b5d71) — confirms `nightshift-agent.sh` is never invoked from inside `nightshift-factory.sh`'s own process for its direct-provider path, and confirms both existing factory-level observation call sites are mutually exclusive within one run.
- `scripts/nightshift-preflight-check.sh:9,147-151,219` (branch: nightshift/35, commit: 92b5d71) — confirms `--derive-id` is already called for admission but its result is not exported for metrics use today.
- `scripts/nightshift-ticket-source.sh:1-180` (branch: nightshift/35, commit: 92b5d71) — full read of the header comment and `--derive-id` branch (45-118) and the `gh` adapter (157-180); confirms `source`/`source_id`/`external_ref` shapes and the no-network-fetch identity-only mode this design reuses.
- `docs/RUN-MEASUREMENTS.md:1-220` (branch: nightshift/35, commit: 92b5d71) — full read; preflight sequencing (8-27), no-Git limitation (31-35), `summary.json` shape example (36-59), repair-count semantics (65-70), usage-capture boundary and Codex/local `null` (71-78), dispatcher-observation role→stage map (83-95), what is never captured (148-156), metrics-failures-non-fatal (159-163), limitations (168-186), works cited (188-201).
- `docs/NIGHTSHIFT-COST-POLICY.md:1-19` (branch: nightshift/35, commit: 92b5d71) — full read; "missing usage or cost information means unknown, not zero" (17-19).
- `routing.json:1-193` (branch: nightshift/35, commit: 92b5d71) — provider/model enumeration confirming `_model()`'s routing-table validation in `scripts/nightshift-run-metrics.py:99-116` has a live source of truth to check against.
- `tests/test-run-metrics.sh:1-84` (branch: nightshift/35, commit: 92b5d71) — full read; confirms the only observed production-shaped Claude envelope in this repo's test fixtures is `{"type":"result","usage":{"input_tokens":7,"output_tokens":3},...}` (line 24), and the existing fixture pattern this ticket's new test file follows.
- `docs/BEHAVIOR-PROOF.md:1-319` (branch: nightshift/35, commit: 92b5d71) — full read; scenario schema (16-19, 21-26), risk taxonomy and safety-sensitive independent challenge requirement (34-40), review-field null-until-actual-review rule (42-48).
- `https://code.claude.com/docs/en/agent-sdk/cost-tracking` — fetched by the controller (not independently re-fetched in this session); relayed content used only under Technical Constraints/Open Questions, never asserted as this codebase's own behavior.
- `https://github.com/openai/codex/blob/main/sdk/typescript/src/events.ts` at blob `f6ad902779bee05ab0fb9b9cc6a2bca59d52c136` — relayed to this session by the controller, not independently fetched; used only under Open Questions, explicitly marked unverified and not implemented against.
