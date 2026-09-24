User-authorized routing continuation. You are the Codex author, provider codex, author_id codex-spec-35. Reuse collected facts in docs/35/product-extractor.out.json and primary-source evidence in this brief; avoid redundant full-source reading. Read only narrow lines needed for citations. Existing draft is unapproved and rejected for scope reduction. Return a concise complete replacement proposal, at most 140 markdown lines and 8 cases. No writes of any kind; artifacts.diff carries JSON {spec_markdown,behavior_scenarios}. Controller integrates exactly and Claude reviews independently. Do not dispatch roles/factory. Explicit permission capability: worker read-only, controller workspace-write.

# Required scope repair, authorized Codex continuation of interrupted spec attempt 3
READ-ONLY PROPOSAL ONLY. Do not call Write/Edit or Bash file writes, including temporary files. No role/factory dispatch. Return complete proposed spec markdown and scenario JSON as a serialized JSON object in artifacts.diff with keys spec_markdown and behavior_scenarios. Controlling session has separately authorized workspace integration. results.spec_path = docs/35/SPEC.md (proposed destination). Do not spend a tool call testing write permissions. A complete returned proposal is SUCCESS pending integration, not a claim of on-disk existence.

The current docs/35/SPEC.md is NOT approved. Its scope reduction is rejected. Replace its draft, recording actual codex author identity. Keep spec CONCISE: maximum 220 markdown lines, ideally 150; no conversation history; source entries only exact path:line-range with branch nightshift/35 commit 92b5d71. Scenario document 8 required cases mapping exactly all 8 upstream ACs, plus safety case only if needed. Keep reviews null. Read docs/BEHAVIOR-PROOF.md for exact schema. Use AD technical documentation style.

MANDATORY repairs:
- Preserve upstream AC1-AC8 verbatim (no weakened substitutes), give stable IDs. Required provider token/cost capture is NOT optional. Only GitHub comments and a token-derived pricing table may be deferred. Actual billed cost unknown remains correct; provider-reported client estimate must be captured if present with truthful provenance.
- Ticket identity includes source, repository, and source_id; external_ref alone collides across repositories. Batch per-observation identity must bind correct ticket; shared/unknown overhead explicit. Persistent atomic ticket JSON summary must exist and rebuild from immutable receipts (not a purely read-only ephemeral report/index only). Always replay authoritative receipts, including events added after an older summary.
- Record orchestrator receipts where available, children, failed calls, retries, resumes. An unmeasured orchestrator explicitly makes incomplete coverage. Preserve fresh/cache-read/cache-write/output categories with non-overlapping total semantics. Explicitly handle parent cumulative receipts vs child receipts: a scope enum alone is insufficient to prevent overlapping totals. Key replay to stable run/invocation/receipt identities; define conflicts conservatively.
- No inferred zero for missing categories/model/pricing; expose known subtotals plus missing-observation counters. Unknown pricing stays unknown; reported estimate is distinct from token-derived estimate and actual invoice.
- Incorporate verified provider formats below. Independent re-fetch is welcome, but do not declare controller-verified primary sources unusable just because not in this repo. Lookup by controller is authoritative project input. The task explicitly requests implementing capture, not proving current code already does it.

Primary source verification by controlling session on 2026-09-15:
1. https://code.claude.com/docs/en/agent-sdk/cost-tracking lines 83-88: total_cost_usd and costUSD are client-side estimates from SDK price table, not authoritative billing; preserve provider estimate source/version where available, billed amount stays unknown. Lines 95-140: result usage covers main-loop tokens only; modelUsage and total_cost_usd include internal subagents; per query result is call total, streaming multiple results are cumulative and need latest not naive sum. This same Claude Code binary backs the Agent SDK. Keep external separately dispatched CLI children distinct from SDK-internal nested subagents; unknown overlap must stay incomplete, never guessed disjoint.
2. Controller command gh api repos/openai/codex/contents/sdk/typescript/src/events.ts returned blob f6ad902779bee05ab0fb9b9cc6a2bca59d52c136. https://github.com/openai/codex/blob/main/sdk/typescript/src/events.ts verified Usage fields: input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens. TurnCompletedEvent is {type:"turn.completed",usage:Usage}. Missing fields on installed older formats stay unknown; events do not report model identity. Actual selected model must not become reported model. Verify total semantics in source/docs, don't guess.

Implement one cohesive extension to existing run metrics and provider boundaries; standard library only. Define precise CLI contract and report schema sufficient for independent tests. Include new test paths in scope with Action CREATE/TEST so RED-lock works. New identifiers explicit proposed and collision-checked. Test red must fail relevant assertions on baseline, not import/syntax. Include authoritative command in Test Plan. At least relevant existing provider/runtime tests remain green; no altering tests to make incomplete features pass.

### Upstream ticket (required source of truth)
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