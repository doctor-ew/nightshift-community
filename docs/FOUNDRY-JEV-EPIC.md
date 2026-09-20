# Epic: Replace cxeng with a measured, configurable engineering workflow on Azure Foundry

Status: **Draft for planning; no implementation or savings claimed**  
Created: 2026-09-20  
Destination: Local planning artifact; upstream project and ticket destination TBD  
Owner, sponsor, budget, target repositories, Azure region, and timeline: TBD

## Outcome

Deliver a work-ready replacement for cxeng that preserves the required engineering stages and evidence, uses configurable Azure Foundry model/runtime integrations, and measures cost and elapsed time per independently accepted ticket. Evaluate Jev as an optional component for focused judgments, routing, and browser interaction. Adopt it only where controlled experiments demonstrate benefit without unacceptable quality loss.

This epic covers the full proposal discussed: baseline measurement, migration architecture, Foundry integration, skill execution, execution tools, Jev evaluation, workflow routing, the third-party gateway, browser QA, and staged rollout. It does not authorize a production deployment or transmission of company data to an external Jev service.

All task IDs below are local planning labels, not published issues or Beads IDs. The eventual upstream tracker remains the source of truth. Every task is open.

## Why this work

We need evidence that a replacement reduces engineering cost and time while preserving correctness. The current cost split, human supervision burden, and failure distribution at work have not been measured in this discussion. No absolute savings target or ROI claim is justified yet.

Jev returns typed choices, scores, and probability judgments rather than generating implementation text. This suggests bounded decisions and evaluation as initial uses, with general models retained for authoring and substantive reasoning. This placement is an architectural proposal, not proof of performance on company engineering work. [S1]

Foundry supports managed agents as well as model access from agents hosted elsewhere. A dedicated hosted agent per skill is therefore an option to evaluate, not a prerequisite for the migration. [S5]

## Evidence and its limits

| Evidence | What it supports | What it does not establish |
|---|---|---|
| LangChain reports about 0.44 seconds and $0.00035 per Jev evaluation, with full agreement on repeated binary judgments in its experiment. It used five fixed weather-agent examples, repeated 100 times. [S2] | A focused evaluator pilot is worth considering. | Accuracy on code, architectural decisions, security review, or hundreds of distinct engineering cases. |
| Browser Use selects operations and observed elements with Jev, using another model when text generation is needed. It documents narrow performance measurements and independent verification. [S3] | A constrained browser-action experiment. | Broad UI reliability or replacement of outcome assertions. |
| The gateway can bypass the generation model for fully closed argument schemas; open-ended arguments still require generation. Its Claude Code path uses hints and explicitly discourages expecting cost/latency savings. It documents added network latency and mixed small-benchmark results. [S4] | A separate, controlled gateway comparison. | A universal drop-in saving across skills, clients, or providers. |
| The reviewed Jev integration lists external service endpoints. [S4] | An external-service integration candidate. | Jev availability in the company's Foundry region, private hosting, or Azure-only processing. |

Treat these as source-reported findings, not independently reproduced results. Archive source revisions during the pilot because product behavior and documentation can change. Avoid interpreting repeatability as correctness.

## Proposed architecture

These are proposed responsibilities, not descriptions of an implemented replacement:

1. **Workflow runner:** stage transitions, durable progress, retries, budgets, evidence, and resume behavior.
2. **Versioned skills:** instructions, required inputs, output contracts, tool permissions, and completion criteria. Keep business workflow instructions independent of the model provider.
3. **Foundry adapter:** configured model deployments, authentication, request/response translation, timeouts, usage collection, and explicit failure handling.
4. **Execution environment:** isolated repository access and bounded tools for search, edits, builds, tests, and source-control operations. Model inference alone is not the proposed execution environment.
5. **Optional decision/evaluation adapter:** Jev or another evaluator behind a replaceable contract; initially observational.
6. **Evidence and observability:** correlated stage/run records, actual tool outcomes, independent review, usage, and attributable human effort.

Start by evaluating one runner with shared configured model deployments. Split skills into separately hosted agents only where lifecycle, scaling, permissions, or ownership justify that decision. Foundry's documented hosting choices support evaluating both approaches. [S5]

Use deterministic checks for mechanically verifiable facts. Do not ask Jev to infer whether a test command passed when the recorded exit status is available. Jev may flag a semantic evidence gap; it must not manufacture missing evidence or grant authorization.

## Scope and boundaries

In scope:

- Inventory and preserve the work team's required cxeng behavior.
- Measure the current baseline and compare a Foundry-backed replacement.
- Keep model/provider choice, budgets, authentication, and fallback configurable.
- Preserve independent tests, review, drift checks, and deployment policy.
- Test Jev for intake classification, evidence-gap screening, failure classification, regression scoring, bounded routing, and browser action selection.
- Independently test the third-party gateway; do not combine its results with a custom Jev integration.
- Document operating costs, human effort, maintenance burden, rollback, and adoption decisions.

Out of scope unless separately approved:

- Replacing substantive code/security review with a Jev score.
- Training a new model or claiming private Jev hosting is available.
- Migrating every team or repository before a representative pilot passes.
- Changing production deployment authorization or deleting retained evidence.
- Making Jev, LangSmith, or any one generation model mandatory for the workflow.

## Decisions to resolve

| Decision | Owner | Resolved by |
|---|---|---|
| Upstream tracker/project and target work repositories | Sponsor | FJ-01 |
| Required cxeng stages, integrations, and compatibility | Engineering owner | FJ-01 |
| Azure-only requirement versus permitted external processing | Company data/security owner | FJ-02 |
| Foundry region, supported deployments, identity, quotas, and billing | Azure owner | FJ-02, FJ-05 |
| Existing runner versus Foundry-hosted runner; agent-per-skill exceptions | Architecture owner | FJ-04 |
| Model choices, budget limits, and fallback policy | Engineering/Azure owners | FJ-05 |
| Quality tolerances, minimum benefit, and acceptable payback period | Sponsor and independent reviewers | FJ-03, FJ-07 |
| Human-time valuation and subscription/API accounting | Sponsor/finance | FJ-03 |

Do not treat missing answers as approval. External Jev experiments may use approved synthetic/public fixtures while company-data eligibility remains unresolved; they cannot establish company-workload performance by themselves.

## Measurement and adoption contract

Proposed primary measures:

- Total experiment spend divided by independently accepted tickets, retaining spend on failed attempts in the numerator.
- Fully loaded cost per accepted ticket, including attributable engineer time, model/API spend, execution infrastructure, and an explicit allocation of ongoing integration overhead.
- Time to acceptance, p50 and p95 when sample size supports them; also report failures and censored runs rather than excluding them.
- Human intervention minutes, repair loops, unnecessary escalations, and missed failures.
- Raw fresh/cache input, cache-write where available, output/reasoning usage where separately reported, provider-reported model, retries, and billing mode.
- For evaluators: false accepts, false rejects, abstentions, agreement with independent labels, and performance by failure category.

Keep authoritative billed amounts, provider estimates, and token-derived estimates separate. Missing usage is unknown, not zero. The local cost policy and measurement documents already describe these distinctions; assess reuse rather than building competing accounting semantics. [S6, S7]

An illustrative bound: if judgment calls represent 10% of total cost, a 90% reduction in that component yields 9% total savings before new overhead. This is arithmetic, not a forecast. Reductions in rework must be measured separately.

Adoption thresholds must be recorded before held-out evaluation. A 30–50-run initial dataset is proposed for feasibility and error discovery, not proof of safety or rare-error rates. Expand it if the adoption decision requires stronger evidence. Do not tune against the final held-out set.

## Task sequence

| ID | Task | Dependencies | Track |
|---|---|---|---|
| FJ-01 | Inventory cxeng and define migration parity | None | Core |
| FJ-02 | Resolve data boundary and Azure feasibility | FJ-01 | Core |
| FJ-03 | Establish baseline accounting and experiment measures | FJ-01 | Core |
| FJ-04 | Define runner, skill, and adapter contracts | FJ-01, FJ-02 | Core |
| FJ-05 | Implement and verify Foundry inference adapter | FJ-03, FJ-04 | Core |
| FJ-06 | Implement isolated execution and resumable workflow | FJ-04, FJ-05 | Core |
| FJ-07 | Build labeled evaluation corpus and freeze criteria | FJ-02, FJ-03 | Shared |
| FJ-08 | Port one complete engineering slice | FJ-06, FJ-07 | Core |
| FJ-09 | Implement optional Jev decision/evaluation adapter | FJ-02, FJ-04, FJ-07 | Experiment |
| FJ-10 | Run Jev evaluator in shadow mode | FJ-08, FJ-09 | Experiment |
| FJ-11 | Pilot intake and failure routing | FJ-10 | Conditional |
| FJ-12 | Benchmark jev-gateway separately | FJ-02, FJ-03, FJ-07 | Optional |
| FJ-13 | Benchmark bounded browser QA | FJ-02, FJ-03, FJ-07, FJ-09 | Optional |
| FJ-14 | Produce economics and quality decision | FJ-08, FJ-10; disposition of FJ-11–13 | Decision |
| FJ-15 | Complete selected migration and controlled rollout | FJ-14 | Core |

### FJ-01 — Inventory cxeng and define migration parity

Deliverable: A migration inventory and selected pilot workload.

Acceptance criteria:

- Identify required stages, skills, tools, ticket systems, repository conventions, authentication, and human approval points from the actual work installation.
- Map each capability to retain, adapt, retire by explicit decision, or defer; record the owner of each decision.
- Select representative bug-fix, feature, and failure-recovery cases and document their acceptance evidence.
- Confirm upstream tracker, target repositories, and baseline version. Do not copy personal environment assumptions into company configuration.

Validation: Walk through one historical accepted ticket and one failed ticket against the inventory.

### FJ-02 — Resolve data boundary and Azure feasibility

Deliverable: Recorded deployment/data decision with evidence and unresolved constraints.

Acceptance criteria:

- Verify available Foundry region, models, quotas, authentication, execution hosting options, and company access requirements.
- Establish whether prompts, code, tool results, and traces may reach each proposed external endpoint; document retention and logging requirements.
- Verify Jev hosting options with authoritative evidence; absence of evidence must not become a claim of Azure/private availability.
- If external Jev is disallowed, preserve the Foundry migration and record a no-adopt or approved alternative-evaluator path.
- Define permitted pilot datasets and the people authorized to approve company-data use.

Validation: Review by the Azure and company data owners; synthetic fixtures alone do not satisfy a company-data approval.

### FJ-03 — Establish baseline accounting and experiment measures

Deliverable: Baseline report and reusable measurement contract.

Acceptance criteria:

- Measure the existing workflow before changing its decisions; capture run/stage identity, outcome, timing, retry cost, usage provenance, and human interventions.
- Separate subscription costs, API consumption, infrastructure, estimates, and actual bills; report unknown values explicitly.
- Include unsuccessful attempts and interrupted runs in aggregate costs and outcome counts.
- Record caching effects, model identity, configuration versions, and workload categories so comparisons are interpretable.
- Agree minimum material benefit, quality tolerances, pilot spend cap, and how human time is valued before comparative runs.

Validation: Reconcile a sample report to underlying run evidence and available billing records; demonstrate an incomplete-usage case.

### FJ-04 — Define runner, skill, and adapter contracts

Deliverable: Architecture decision and versioned interface specifications.

Acceptance criteria:

- Define skill inputs, outputs, evidence requirements, failure states, permissions, and ownership.
- Separate orchestration, model inference, tool execution, and semantic evaluation responsibilities.
- Define configured provider/model selection and explicit fallback; record why any skill requires a distinct hosted agent.
- Specify durable state, resume behavior, idempotency, cancellation, budget accounting, and retry exhaustion.
- Define optional evaluator outcomes including abstention/unavailable; evaluator failure cannot silently become a passing gate.

Validation: Tabletop successful, failed, interrupted, and resumed tickets without relying on provider-specific role instructions.

### FJ-05 — Implement and verify Foundry inference adapter

Deliverable: Configurable adapter and deployment-specific verification receipt.

Acceptance criteria:

- Implement the agreed interface against explicitly configured Foundry deployments and company-approved identity.
- Record active billing mode and model provenance; do not silently substitute subscription or API billing.
- Handle throttling, authentication failure, timeouts, cancellation, malformed outputs, and unavailable deployment without hiding errors or losing accounting.
- Verify the required tool-call and output-contract behavior on each selected deployment; do not infer compatibility from API naming alone.
- Keep credentials out of artifacts and retain bounded, attributable retry records.

Validation: Offline contract/error tests plus an approved live smoke test with receipts and measured cost.

### FJ-06 — Implement isolated execution and resumable workflow

Deliverable: Pilot runner with bounded execution tools and durable evidence.

Acceptance criteria:

- Provide isolated checkout/worktree or equivalent execution state with scoped repository permissions.
- Execute the selected build/test/search/edit/source-control tools and retain real outcomes.
- Preserve stage ordering, independent review, drift checks, and company deployment policy.
- Resume after interruption without duplicating irreversible side effects or resetting consumed budgets.
- Keep authorization enforcement in executable policy; model confidence cannot expand tool permissions.

Validation: Exercise successful execution, test failure, review rejection, exhausted repair budget, interrupted resume, and denied operation.

### FJ-07 — Build labeled evaluation corpus and freeze criteria

Deliverable: Versioned corpus, rubric, split manifest, and preregistered comparison plan.

Acceptance criteria:

- Start with 30–50 representative historical runs where available; explicitly label synthetic or public substitutes.
- Include known omissions, incorrect acceptance claims, tool failures, unnecessary actions, and successful cases across selected task categories.
- Have independent reviewers label focused questions and resolve or retain disagreements explicitly.
- Separate rubric development, threshold calibration, and held-out evaluation by ticket family to reduce leakage.
- Freeze scoring, tolerances, timeout budgets, model versions, comparison procedure, and expansion criteria before held-out runs.

Validation: Audit labels against source evidence and verify no target answer/held-out verdict reaches the evaluated agent.

### FJ-08 — Port one complete engineering slice

Deliverable: A Foundry-backed ticket flow compared with the existing workflow.

Acceptance criteria:

- Complete intake through specification, implementation, tests, review, and handoff for the selected pilot slice.
- Preserve the agreed cxeng acceptance behavior and emit reviewable artifacts at every required stage.
- Compare against the baseline using independent acceptance and equivalent starting revisions, budgets, and task inputs.
- Record all failures, interventions, configuration differences, and remaining parity gaps.

Validation: Independent end-to-end review of accepted and failed pilot runs. A successful model call does not satisfy this task.

### FJ-09 — Implement optional Jev decision/evaluation adapter

Deliverable: Replaceable adapter disabled by default for workflow control.

Acceptance criteria:

- Support agreed bounded choice/score/judgment requests with versioned state and rubric provenance.
- Validate responses; record latency, cost provenance, confidence, timeout, and abstention without treating confidence as verified correctness.
- Send only permitted data and retain payload/provenance records according to the FJ-02 policy.
- Bound request size and detect missing/truncated evidence; abstain rather than silently score incomplete state as complete.
- Demonstrate workflow operation with Jev disabled or unavailable.

Validation: Contract tests for malformed output, timeout, missing evidence, and denied data egress, plus an approved live evaluation fixture.

### FJ-10 — Run Jev evaluator in shadow mode

Deliverable: Held-out evaluator report and adopt/narrow/reject decision.

Acceptance criteria:

- Score focused criteria such as evidence support, apparent acceptance-criteria coverage, and trace/task alignment without changing workflow behavior.
- Compare with independent labels and the existing evaluator under the same evidence and rubric.
- Report false accepts, false rejects, abstentions, latency, cost, and results by failure category with sample-size limitations.
- Distinguish repeatability from correctness and repeat judgments only when the measurement question requires it.
- Recommend the narrowest justified use; do not replace independent engineering gates based solely on this pilot.

Validation: Review held-out disagreement cases and verify no shadow result influenced execution or ground-truth labeling.

### FJ-11 — Pilot intake and failure routing

Deliverable: One bounded, reversible routing experiment.

Acceptance criteria:

- Choose one decision supported by FJ-10 evidence: intake specialist selection, scope escalation, or classification into an existing recovery path.
- Prefer deterministic routing where existing facts suffice; document why semantic classification is needed for the selected case.
- Restrict choices to configured allowed paths; preserve budgets, required review, and authorization.
- Calibrate abstention/fallback thresholds on development data and freeze them before evaluation.
- Measure total accepted-ticket cost/time, wrong-route recovery, and unnecessary escalation against the baseline; retain a disable switch.

Validation: Held-out comparison including ambiguous cases, service failure, misleading tool output, and confidently incorrect decisions.

### FJ-12 — Benchmark jev-gateway separately

Deliverable: Client-specific compatibility and economics report; no default rollout.

Acceptance criteria:

- Pin a reviewed gateway revision and inspect credential forwarding, data sent to Jev, context handling, and logging before approved use.
- Verify the actual work client and Foundry authentication/wire protocol; documented generic compatibility is insufficient.
- Compare gateway off/on using equivalent clean starting states, randomized run order, fixed budgets, and independent hidden acceptance checks.
- Record direct, forced, hint, and passthrough frequencies; separate saved model calls from calls that still invoke the generation model.
- Include added latency, cache changes, retries, acceptance rate, and full cost; do not promote token reductions alone as savings.
- Mark unsupported or uneconomic client paths as rejected without blocking the core migration.

Validation: Reproducible receipts across bug and feature cases; ensure one run cannot inspect another run's solution.

### FJ-13 — Benchmark bounded browser QA

Deliverable: A narrow UI experiment and supported-widget inventory.

Acceptance criteria:

- Select approved repeatable UI tasks and compare against the current browser approach under equivalent conditions.
- Use observed controls and constrained actions; keep text generation separately attributable.
- Verify outcomes with assertions independent of the model's completion choice.
- Include stale page state, loading, unexpected dialogs, and unsupported controls with bounded failure behavior.
- Report success rate, elapsed time, calls, generation cost, and intervention; define timing boundaries including setup separately.
- Preserve application permissions and prevent benchmark runs from performing unapproved irreversible actions.

Validation: Repeated controlled tasks and failure cases, with traces and independent outcome evidence.

### FJ-14 — Produce economics and quality decision

Deliverable: Decision memo for the Foundry replacement and each Jev experiment independently.

Acceptance criteria:

- Compare baseline, Foundry-only, and each measured Jev variant without conflating model, prompt, runner, or gateway changes.
- Include implementation/maintenance cost, infrastructure, subscriptions/API costs, human effort, unknowns, and uncertainty.
- Report quality and time alongside cost; identify whether the apparent saving survives failed attempts and recovery.
- Mark each candidate adopt, narrow, investigate further, or reject with supporting evidence and an owner.
- If integration cost is known and recurring net savings are positive, estimate payback; otherwise report payback as unknown or absent.
- Explicitly disposition optional experiments as completed, deferred, or rejected rather than leaving ambiguous dependencies.

Validation: Independent review of calculations and evidence. No rollout on an unmeasured savings claim.

### FJ-15 — Complete selected migration and controlled rollout

Deliverable: Work-ready selected scope, operating guide, rollback procedure, and acceptance report.

Acceptance criteria:

- Complete remaining agreed parity work and migrate only approved repositories, skills, and integrations.
- Use versioned configuration, explicit deployment/model selection, spend limits, and observable fallback.
- Document setup, identity, billing, incident handling, failure receipts, resume, and restoration of the previous workflow.
- Start with a limited cohort and compare live accepted-ticket quality/cost/time with the frozen baseline and rollback triggers.
- Enable only experiments adopted by FJ-14; rejection of Jev does not invalidate a successful Foundry migration.
- Obtain explicit production approval immediately before any production deployment, with exact target and command presented.

Validation: Acceptance by the work engineering owner, exercised rollback/resume, and retained independent verification receipts.

## Epic completion criteria

- The agreed replacement scope completes real work tickets with independent acceptance evidence.
- Foundry hosting/inference, tool execution, identity, data boundary, and operational ownership are resolved and documented.
- Cost and elapsed-time comparisons retain failed work, human intervention, and accounting uncertainty.
- Every Jev experiment has an explicit evidence-backed disposition; universal adoption is not required.
- Required gates and authorization remain intact, and the previous workflow can be restored.
- No task or epic is marked complete solely because a plan, adapter smoke test, or favorable token chart exists.

## Sources

External sources were reviewed during the 2026-09-20 discussion. Capabilities and reported results must be revalidated and pinned when implementation starts.

- **S1 — TypeSafe:** [Jev introduction and typed primitives](https://docs.typesafe.ai/introduction).
- **S2 — LangChain:** [Jev-as-a-Judge for Agent Evals](https://www.langchain.com/blog/jev-agent-evals-langsmith). Narrow weather-agent evaluation, source-reported results.
- **S3 — Browser Use:** [jev-ultrafast README and evidence limits](https://github.com/browser-use/jev-ultrafast).
- **S4 — Third-party gateway:** [jev-gateway README](https://github.com/vinilana/jev-gateway), particularly hosting endpoints, routing modes, Claude Code, tradeoffs, and benchmark limitations. This is not a TypeSafe-endorsed integration according to its README.
- **S5 — Microsoft:** [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview).
- **S6 — Local policy:** [Authentication and usage policy](NIGHTSHIFT-COST-POLICY.md), especially accounting meanings. A design input, not evidence of the work installation's behavior.
- **S7 — Local measurement design:** [Run measurements](RUN-MEASUREMENTS.md) and [efficiency roadmap](EFFICIENCY-ROADMAP.md). Assess current implementation and reuse before assigning changes; historical issue references are not newly created tasks.
