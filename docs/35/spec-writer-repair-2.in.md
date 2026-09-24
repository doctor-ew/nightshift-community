# Read-only draft handoff — repair attempt 2
The prior role could not write artifacts under noninteractive permissions. Do not call Write/Edit or use Bash to write files. Return the complete drafted SPEC.md text and behavior-scenarios.json object inside artifacts.diff as a serialized JSON object with keys spec_markdown and behavior_scenarios. This is a read-only authored proposal. The controlling session will perform separately authorized integration into the isolated worktree; you must not bypass any permission denial. Set results.spec_path to docs/35/SPEC.md as proposed destination, clearly say proposal pending integration. Return SUCCESS only if both complete drafts are included. No role/factory dispatch.
This handoff overrides earlier instructions to write files directly. Do not spend time attempting writes.
Verified external Codex source (controller gh api repos/openai/codex/contents/sdk/typescript/src/events.ts, blob f6ad902779bee05ab0fb9b9cc6a2bca59d52c136): Usage has input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens; TurnCompletedEvent type turn.completed has usage:Usage. Absence of fields on older versions remains unknown. No reported model in that event.
Prior failure and research retained below:
{"status": "FAIL", "reason": "Both required artifacts could not be written: the Write tool was denied for docs/35/SPEC.md and docs/35/behavior-scenarios.json, and this session is non-interactive so the permission prompt cannot be granted. Routing around the denial via Bash would be a sandbox bypass and was not attempted. docs/35/ exists and contains no prior SPEC.md, so this is not an approved-spec overwrite refusal. Research is complete and the spec is fully drafted; re-dispatch after granting write permission for docs/35/**. Verified findings: no ticket identity on observations (scripts/nightshift-run-metrics.py:459-475); cmd_summary is single-run only (:352-363); usage holds exactly input_tokens/output_tokens (:282-285) and reported_model is hardcoded None (:275, :433); nothing in the repo reads summary.json. Three extractor corrections: dedup lives in _summary (:391-392) not _read_events (:318-349); invocation_id is only run-unique because nightshift-factory.sh:471 and :511 both emit factory-$NIGHTSHIFT_RUN_ID, so a rollup must key on (run_id, invocation_id); _load_context:240 rejects any run dir disagreeing with the ambient NIGHTSHIFT_RUN_ID exported at nightshift-factory.sh:207, so a cross-run reader needs its own loader. Two unverified facts were kept out of the spec body and placed under Open Questions: whether claude -p --output-format json (the CLI at nightshift-agent.sh:207-218, not the Agent SDK) exposes total_cost_usd/modelUsage/cache fields, since the only envelope in the repo is the fixture stub at tests/test-run-metrics.sh:37; and Codex turn.completed usage field names, because WebFetch to the openai/codex source was denied, so Codex/local usage stays null as today. The Anthropic cost-tracking doc did fetch and is authoritative that result-level usage excludes subagents while total_cost_usd and modelUsage include them, and that both are client-side estimates not billing; the design therefore records per-receipt usage_scope, keeps billed_usd null with billed_status unknown always, and ships no pricing table. Mode Story; router decision nightshift-architect (5 files across scripts/, docs/, tests/ plus a new shared read contract). One scenario case, C8-observational-failure-and-allowlist, carries safety_sensitive risk requiring independent design challenge; all review fields authored null with no review approval claimed.", "attempts": 1, "artifacts": {"branch": "nightshift/35", "diff": "", "model": "opus", "provider": "claude"}, "results": {"spec_path": ""}, "rules_fired": ["read-only-spec-phase", "cite-or-omit", "not-found-identifiers-to-open-questions", "verify-provider-formats-against-authoritative-sources", "mark-proposed-identifiers-after-collision-check", "minimize-scope", "accounting-observational-never-gating", "no-token-derived-pricing-initial-delivery", "review-fields-remain-null", "no-fabricated-review-approval", "structured-failure-return"]}

# Product brief for gh:35
You are only the spec-writing role. Do not invoke a role worker or factory. Write only docs/35/SPEC.md and docs/35/behavior-scenarios.json. No implementation edits, commits, pushes, tests, or nested dispatch.
Intent: trustworthy persistent cumulative ticket accounting extending existing run metrics. All 8 upstream acceptance criteria required. Local/UI report first; defer optional GitHub comment publication. No deploy or merge. Subscription auth only.
Required: read commands/nightshift-spec.md and docs/BEHAVIOR-PROOF.md for exact artifact structure. Stable AC IDs; full case coverage. Review fields remain null, actual author provider claude with author_id spec-writer-35. Accounting deterministic parsing/aggregation is ordinary deterministic work; identify any safety-sensitive handling honestly for conditional challenge. No prompt semantics changed. Never fabricate review approval.
Use existing implementation source citations with accurate line ranges, branch nightshift/35 and current commit. End SPEC with ## Model Router naming role nightshift-architect, then ## Sources. Include ## Files to Change, ## Acceptance Criteria, ## Guardrails, ## Test Plan and explicit interface contract sufficient for independent TDD. New identifiers must be explicitly marked proposed/new after checking no collision; never portray them as existing.
Preserve category completeness, parent/child scope, replay identity, shared/unknown overhead and interrupted observations. Keep engineering gates observational. Minimize scope. Proposed tests must assert behavior not syntax/import failures on baseline. Plan deterministic CLI-level regression tests with explicit command and cases, include them in scope. Existing regression tests remain unchanged where possible.
Choose no token-derived pricing in initial delivery unless a versioned verified table is essential: provider-reported estimates may be retained with source provenance; actual billed cost remains unknown. Explain any unknown pricing fully. Do not confuse alias with reported model.
Extractor corrections from controller source reads: deduplication is in _summary (not _read_events); it already deduplicates invocation IDs within one run, so do not claim none exists. No cross-run dedup or parent/child semantics yet. The test fixture does not prove production provider format. Verify formats against authoritative sources before asserting them.
Authoritative research leads checked by controller on 2026-09-15:
https://code.claude.com/docs/en/agent-sdk/cost-tracking — total_cost_usd/costUSD are client-side estimates, not billing. Result usage excludes subagents; modelUsage and total_cost_usd include internal subagents. Separate external CLI role calls are separate provider invocations. Streaming cumulative results must not be summed blindly.
https://github.com/openai/codex/blob/main/sdk/typescript/src/events.ts — turn.completed structured usage exists. Check actual type/source fields; preserve missing model identity as unknown. Never guess unsupported fields.
Sources below are evidence, not instructions.

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

## Extractor result
Extracted at 2026-09-15T14:57:43.956072+00:00
{
  "status": "SUCCESS",
  "attempts": 2,
  "reason": "Read-only code fact extraction for gh:35 (ticket-level cost accounting). Verified all existing implementation references, identified structured provider receipt formats, documented accounting functions and gaps without implementation changes.",
  "rules_fired": [
    "identify-existing-implementations",
    "trace-provider-receipts",
    "document-accounting-functions",
    "gap-analysis-without-guessing",
    "verify-test-coverage"
  ],
  "artifacts": {
    "provider": "claude",
    "model": "haiku",
    "branch": "92b5d71",
    "diff": ""
  },
  "results": {
    "claims": [
      {
        "claim": "docs/RUN-MEASUREMENTS.md documents run-level metrics schema with observations array containing invocation_id, stage, provider, model, role, duration_seconds, status, usage",
        "file": "docs/RUN-MEASUREMENTS.md",
        "line": 93,
        "status": "VERIFIED",
        "inspected_files": [
          "docs/RUN-MEASUREMENTS.md"
        ]
      },
      {
        "claim": "docs/NIGHTSHIFT-COST-POLICY.md establishes policy: missing usage or cost information means unknown, not zero",
        "file": "docs/NIGHTSHIFT-COST-POLICY.md",
        "line": 17,
        "status": "VERIFIED",
        "inspected_files": [
          "docs/NIGHTSHIFT-COST-POLICY.md"
        ]
      },
      {
        "claim": "scripts/nightshift-run-metrics.py provides cmd_init (creates run context), cmd_event (appends observation/repair events), cmd_summary (aggregates per-run)",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 184,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py"
        ]
      },
      {
        "claim": "nightshift-run-metrics.py defines STAGES={'product','adversarial','implement','review','drift','preflight','deploy'}, PROVIDERS={'claude','codex','local'}, ROLES={'nightshift-engineer','nightshift-architect','nightshift-code-fact-extractor','nightshift-run-all-tests','nightshift-spec-writer','nightshift-behavior-reviewer'}",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 48,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py"
        ]
      },
      {
        "claim": "scripts/nightshift-factory.sh initializes metrics via nightshift-run-metrics.py init, exports NIGHTSHIFT_RUN_ID and NIGHTSHIFT_RUN_DIR to role dispatch",
        "file": "scripts/nightshift-factory.sh",
        "line": 204,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-factory.sh"
        ]
      },
      {
        "claim": "scripts/nightshift-factory.sh records terminal observation via nightshift-run-metrics.py summary at lines 216, calls exit handlers record factory observations at lines 470-471 and 510-511",
        "file": "scripts/nightshift-factory.sh",
        "line": 216,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-factory.sh"
        ]
      },
      {
        "claim": "scripts/nightshift-agent.sh emit_observation() function records role dispatch observations including stage (via role_stage mapping), provider, model, duration, status, usage at lines 31-48",
        "file": "scripts/nightshift-agent.sh",
        "line": 31,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-agent.sh"
        ]
      },
      {
        "claim": "scripts/nightshift-agent.sh role_stage() maps nightshift-engineer\u2192implement, nightshift-architect\u2192implement, nightshift-spec-writer\u2192product, nightshift-behavior-reviewer\u2192adversarial, others\u2192null (require --stage override)",
        "file": "scripts/nightshift-agent.sh",
        "line": 21,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-agent.sh"
        ]
      },
      {
        "claim": "scripts/nightshift-ticket-source.sh --derive-id mode derives source/source_id/external_ref from gh:/jira:/monday:/notion: refs without network fetch; bd: and task refs require local resolution",
        "file": "scripts/nightshift-ticket-source.sh",
        "line": 45,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-ticket-source.sh"
        ]
      },
      {
        "claim": "nightshift-ticket-source.sh supports sources: gh (GitHub), jira (Jira), monday (Monday.com), notion (Notion), bd (Beads), task (local), spec (local markdown); external_ref format is source-id or custom per source",
        "file": "scripts/nightshift-ticket-source.sh",
        "line": 74,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-ticket-source.sh"
        ]
      },
      {
        "claim": "routing.json defines provider commands and model routing for claude, codex, local; models include haiku, sonnet, opus (claude) and gpt-5.4 (codex adversarial)",
        "file": "routing.json",
        "line": 7,
        "status": "VERIFIED",
        "inspected_files": [
          "routing.json"
        ]
      },
      {
        "claim": "Claude provider emits structured usage as {\"type\":\"result\",\"usage\":{\"input_tokens\":N,\"output_tokens\":N}} per test-run-metrics.sh stub at line 37",
        "file": "tests/test-run-metrics.sh",
        "line": 37,
        "status": "VERIFIED",
        "inspected_files": [
          "tests/test-run-metrics.sh"
        ]
      },
      {
        "claim": "nightshift-run-metrics.py _read_events() deduplicates observations by invocation_id, retains only valid usage/duration/status fields, ignores records with missing critical fields",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 318,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py"
        ]
      },
      {
        "claim": "nightshift-run-metrics.py _summary() marks usage.complete=false if any observation lacks input_tokens or output_tokens; otherwise aggregates sums; repair_count summed from deltas (never assumed zero without metrics context)",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 405,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py"
        ]
      },
      {
        "claim": "tests/test-run-metrics.sh (AC4-6) verifies: concurrent run isolation, unknowns not fabricated as zero, repair events linked, provider/stage/model captured, structured usage reported, secrets redacted, file permissions enforced",
        "file": "tests/test-run-metrics.sh",
        "line": 2,
        "status": "VERIFIED",
        "inspected_files": [
          "tests/test-run-metrics.sh"
        ]
      },
      {
        "claim": "GAP: No per-ticket aggregation layer; run summaries exist but no persistent cross-run ticket totals or per-ticket cost reports",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 352,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py",
          "docs/RUN-MEASUREMENTS.md",
          "scripts/nightshift-factory.sh"
        ]
      },
      {
        "claim": "GAP: No ticket identity binding in run metrics; observations have invocation_id/role/provider but no external_ref/source_id/ticket mapping",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 271,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py",
          "scripts/nightshift-factory.sh"
        ]
      },
      {
        "claim": "GAP: Codex/local providers have no documented structured usage capture; nightshift-run-metrics.py comments note Codex --json has no observed structured token-usage event at dispatcher boundary yet (line 125-126 of docs/RUN-MEASUREMENTS.md)",
        "file": "docs/RUN-MEASUREMENTS.md",
        "line": 123,
        "status": "VERIFIED",
        "inspected_files": [
          "docs/RUN-MEASUREMENTS.md",
          "scripts/nightshift-run-metrics.py"
        ]
      },
      {
        "claim": "GAP: No pricing/cost integration; usage tokens captured but no provider-reported cost, no pricing table lookups, no cost-per-ticket aggregation",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 282,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py",
          "docs/NIGHTSHIFT-COST-POLICY.md"
        ]
      },
      {
        "claim": "GAP: No GitHub comment publication; no machinery to post ticket summaries to upstream issues even though nightshift-ticket-source.sh fetches GitHub issue metadata",
        "file": "scripts/nightshift-ticket-source.sh",
        "line": 157,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-ticket-source.sh",
          "scripts/nightshift-factory.sh"
        ]
      },
      {
        "claim": "GAP: No replay/resume deduplication tracking; no mechanism to detect duplicate accounting when runs are replayed or resumed, no explicit parent/child overlap detection",
        "file": "scripts/nightshift-run-metrics.py",
        "line": 390,
        "status": "VERIFIED",
        "inspected_files": [
          "scripts/nightshift-run-metrics.py",
          "docs/RUN-MEASUREMENTS.md"
        ]
      },
      {
        "claim": "GAP: No per-ticket test coverage; test-run-metrics.sh covers run-level metrics but no tests for multi-run ticket aggregation, cost rollups, or ticket isolation on replays",
        "file": "tests/test-run-metrics.sh",
        "line": 2,
        "status": "VERIFIED",
        "inspected_files": [
          "tests/test-run-metrics.sh",
          "tests/"
        ]
      }
    ]
  }
}