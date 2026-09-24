Read-only product identifier extraction for gh:35. Do not invoke any role worker or factory. Verify all existing implementation references and relevant accounting functions/tests with file, line, inspected_files evidence. Identify existing structured provider receipt formats and gaps without guessing. No implementation edits.

Report persistent token usage and cost per ticket
## Problem

Nightshift needs a trackable cost and token report for each upstream ticket. Overall ticket totals are required; segment/stage breakdowns and ticket comments are desirable. A machine-readable local report must be available for a UI to consume.

The existing run measurements provide a foundation, but do not yet provide complete ticket-level cost accounting across runs. Extend that implementation rather than create an unrelated accounting system.

## Required scope

- Associate provider invocations with the upstream source/repository/ticket identity and run. Aggregate all runs for a ticket, including retries, repairs, failed calls, and resumed execution.
- Capture orchestrator and child-agent usage at provider boundaries where structured receipts are available. Verify actual provider formats before implementing adapters. Explicitly report unavailable usage; never infer zero.
- Preserve fresh input, cache-read, cache-write, and output token categories when supplied. Define total-token semantics so cached tokens are not counted twice.
- Record provider-reported dollar cost where available. If deriving cost from tokens, use a versioned pricing source and actual reported model identity; unknown pricing stays unknown. Distinguish reported cost, estimated equivalent cost, and actual billed cost. Subscription estimates must not be presented as invoices.
- Extend the existing private immutable run events and atomic JSON summaries with persistent ticket aggregation and a documented read interface suitable for the UI. The report must survive process restart and be reconstructable from receipts.
- Prevent duplicate accounting on replay/resume and when parent receipts include child usage. Attribute batch work to the correct ticket; shared or unattributed overhead must be explicit.
- Show known subtotals alongside explicit usage/pricing completeness and missing-observation counts. A partial amount must never be labelled a complete total.
- Keep accounting observational: collection/report failures must not change engineering gate results. Store only allowlisted accounting metadata, not prompts, transcripts, or credentials.

## Should have

- Capture validated stage attribution immediately, retaining an explicit unknown stage when necessary; expose per-stage/provider/model breakdowns where practical.
- Publish or update a compact GitHub ticket comment from the same persisted report, with totals, completeness, run count, and a report reference. Make publication idempotent and retain a local report if publication fails. Keep accounting provider/source-neutral; Jira and other writeback adapters may follow separately.

## Acceptance criteria

1. Two runs for one ticket produce one correct cumulative report, including failed attempts, without mixing another ticket's usage.
2. Replaying receipts, rebuilding summaries, or resuming a run does not duplicate usage or cost.
3. Parent/child overlap and cached-token categories have explicit semantics and regression coverage.
4. Missing usage, missing model identity, and missing pricing produce explicit incomplete reports, never fabricated zero cost or a misleading complete total.
5. Available orchestrator usage is included; an unmeasured orchestrator visibly makes coverage incomplete.
6. A documented machine-readable read operation returns persisted ticket totals and provenance after restart. Interrupted runs retain already-recorded usage.
7. Stage metadata is retained where known, with overall totals consistent with any breakdown.
8. Tests cover ticket isolation, aggregation, replay/resume, pricing provenance, partial coverage, and accounting I/O failures; relevant existing runtime/provider tests remain green.

## Existing implementation references

- docs/RUN-MEASUREMENTS.md
- docs/NIGHTSHIFT-COST-POLICY.md
- scripts/nightshift-run-metrics.py
- scripts/nightshift-factory.sh
- scripts/nightshift-agent.sh
- scripts/nightshift-ticket-source.sh

## Delivery priority

Ship trustworthy persisted per-ticket accounting and the UI-consumable report first. Stage presentation and automatic upstream comments are secondary and must not displace required accounting correctness.