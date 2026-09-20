# Epic: Nightshift efficiency with RTK and Jev

Status: Core implementation verified (NJ-01–06); empirical savings and experiments pending.
Updated: 2026-09-20. Scope: this Nightshift repository and its existing runtimes.

## Outcome

Reduce cost and time per independently accepted ticket with RTK output compression and Jev evaluation. Preserve raw evidence, command outcomes, existing review gates, configurable providers, and explicit opt-outs. Azure/Foundry and the work cxeng migration are separate work and are not dependencies of this epic. The historical filename is retained to preserve existing links.

## Architecture and defaults

- RTK: default enabled when available, restricted to verified command families. Missing RTK falls back visibly to normal execution. Preserve full output and the real exit status; expose a raw-output bypass. Do not filter machine protocols, exact source inspection, or authoritative review diffs.
- Jev: default enabled once configured, initially shadow evaluation only. Record judgments without changing review/test/drift gates. Missing credentials, malformed results, or service failure produce an unavailable/skipped receipt; normal engineering gates still run. Provide project and per-run opt-outs.
- Independent controls: compression, evaluation, and experimental decision/tool routing must be independently selectable. Do not install global hooks or switch the coding provider to use either feature.
- External evaluation: configure endpoint, model, credential environment variable, bounded timeout and input limits. Credentials and raw request bodies must not appear in receipts. Use only approved evaluation data; this epic is not authorization to send arbitrary repository contents externally.
- Preserve existing accounting provenance. Compression byte ratios and estimated token savings are not billed-dollar savings. Retain failed attempts, retries, and human intervention in comparisons.

The core adapters implement these defaults. See the [operating guide](EFFICIENCY-ADAPTERS.md) and [verification report](efficiency/VERIFICATION.md) for supported paths and limits.

## Evidence and limits

RTK filters shell-command output locally; filters may truncate matches, trim tracebacks, and reduce diff context. Its reported savings are output-byte reduction, and token counts are estimates. This motivates an allowlist and raw evidence retention. [R1, R2]

Jev returns typed choices/scores/judgments. LangChain's promising cost and latency results cover five weather-agent examples with repeated judgments, not representative code-review accuracy. Use shadow evaluation and independent labels before allowing decisions to affect work. [J1, J2]

The third-party Jev gateway can skip generation only for closed argument schemas; ordinary open-ended arguments still need a generation model. Its documented tradeoffs include network latency and mixed benchmark outcomes. Browser Use demonstrates bounded action selection but still requires independent outcome verification. Both remain separate experiments. [J3, J4]

## Tasks and acceptance criteria

All IDs below are local planning labels, not published tracker issues. They supersede the previous FJ planning sequence. No task is complete without verification evidence.

| ID | Task | Dependencies |
|---|---|---|
| NJ-01 | Define configuration, raw evidence, and measurement contracts | None |
| NJ-02 | Implement RTK execution wrapper and raw bypass | NJ-01 |
| NJ-03 | Integrate RTK guidance/capability into Nightshift runtime | NJ-02 |
| NJ-04 | Implement configurable Jev shadow evaluator | NJ-01 |
| NJ-05 | Integrate evaluation receipts and opt-outs | NJ-04 |
| NJ-06 | Verify failure behavior and document operation | NJ-03, NJ-05 |
| NJ-07 | Run controlled cost/quality comparison | NJ-06 |
| NJ-08 | Pilot bounded Jev workflow routing | NJ-07 |
| NJ-09 | Benchmark third-party jev-gateway separately | NJ-07 |
| NJ-10 | Benchmark bounded browser QA | NJ-07 |
| NJ-11 | Record adoption decisions and rollout | NJ-07; disposition of NJ-08–10 |

### NJ-01 — Configuration and evidence contracts

Acceptance: separate project/environment/per-run settings with documented precedence; default-on when configured/available; visible bypass/unavailable states; bounded resources; immutable run-specific raw output and receipts; distinguish real command status from adapter status. Preserve existing model/auth/billing selection. Record version/provenance and unknown costs honestly.
Validation: configuration fixtures including opt-outs, invalid values, unavailable tools, and incomplete accounting.

### NJ-02 — RTK wrapper

Acceptance: execute eligible commands once, preserve raw stdout/stderr and exit status, return compressed agent-facing output with evidence paths. Restrict supported commands and bypass unsafe/machine-parsed/exact-evidence forms. Filtering failure must not re-execute a command. Missing RTK must preserve ordinary behavior. No global hook installation.
Validation: offline fake RTK/command fixtures exercising success, failure, bypass, filter failure, missing binary, raw recovery, quoting, and secrets in configuration.

### NJ-03 — Runtime integration

Acceptance: expose the wrapper through the normal Nightshift command surface and runtime instructions; use capability detection; preserve provider-neutral role prompts; independent project/per-run opt-outs. No claim that native non-shell tools are automatically compressed.
Validation: launcher/help/instruction tests and representative supported command smoke tests without paid model calls.

### NJ-04 — Jev adapter

Acceptance: configurable service/model/credential reference; typed rubric and explicit input artifact; bounded payload and network timeout; validate result shape; record input/rubric hashes, status, latency, model provenance, and available usage. No raw prompts or keys in receipts. No silent truncation or invented cost/confidence. Shadow-only output cannot become a PASS gate.
Validation: mocked service fixtures for success, malformed JSON/schema, timeout, HTTP error, oversized input, missing credentials, disabled mode, and endpoint validation.

### NJ-05 — Evaluation integration

Acceptance: supported Nightshift invocation with default-on configured evaluation, explicit opt-out, and visible unavailable/skipped receipts. Use explicit evidence inputs rather than indiscriminately uploading the repository or transcript. Preserve independent engineering gates and ordinary run exit status. A service outage must not pass or fail an engineering gate.
Validation: end-to-end offline evaluation invocation and receipt checks for enabled/disabled/unavailable cases.

### NJ-06 — Verification and operating guide

Acceptance: appropriate regression tests, review findings resolved, setup/opt-out/raw-recovery documentation, config examples grounded in implemented interfaces, and clear distinction between mocked integration and live service verification. No live spend or company-data use inferred from implementation approval.
Validation: targeted suites plus existing affected launcher/provider checks; retain results and remaining limits in an implementation report.

### NJ-07 — Controlled comparison

Acceptance: compare baseline, RTK only, Jev only, and both on equivalent starting revisions with pinned versions/models and independent acceptance. Start with 30–50 representative labeled runs where feasible, separating synthetic data from field evidence. Freeze rubrics and thresholds before held-out runs. Measure accepted-ticket cost/time, input/cache/output usage, retries, human intervention, lost evidence, false accepts/rejects, abstentions, and service overhead. Report failures and unknown billing, not just successful runs or byte savings.
Validation: independently inspect disagreements and reconcile metrics to retained receipts. Pilot sample size is not proof of rare-error safety. Live benchmark depends on credentials, budget, and approved data; leave explicitly pending if unavailable.

### NJ-08 — Bounded workflow routing

Acceptance: select one evidenced semantic decision (intake specialist, scope escalation, or existing recovery route); use deterministic logic where sufficient; preserve budgets and authorization; calibrated abstention and fallback; reversible opt-out. No default gate authority from shadow-evaluation success alone.
Validation: held-out cases including ambiguous and confidently wrong decisions. Adopt/narrow/reject based on total outcomes.

### NJ-09 — Gateway experiment

Acceptance: pin/audit gateway; verify actual Nightshift client compatibility; compare off/on in isolated equivalent runs; account for direct/forced/hint/passthrough modes, cache changes, latency, retries, and success rates. Never infer subscription bill savings from token reductions alone.
Validation: hidden acceptance checks across bug and feature work; explicit adopt/narrow/defer/reject decision. Not required for core RTK/evaluation delivery.

### NJ-10 — Browser experiment

Acceptance: bounded approved UI tasks, observed controls, separately attributable text generation, independent outcome assertions, and handling of stale state/unsupported widgets. Preserve permissions and log timing boundaries.
Validation: repeated tasks and failure cases against the existing browser approach; explicit adopt/narrow/defer/reject decision. Not required for core delivery.

### NJ-11 — Adoption and rollout

Acceptance: separate decisions for RTK, Jev evaluation, routing, gateway, and browser work; retain default-on configured evaluation and allowlisted compression with explicit opt-outs where verification supports rollout; document rejected/deferred experiments. Include integration maintenance cost and rollback instructions. Preserve existing gates and production approval requirements.
Validation: limited cohort evidence and exercised disable/raw-recovery paths. Do not claim savings or whole-epic completion before NJ-07 and the decision record exist.

## Completion

Core implementation milestone: NJ-01–06 completed and [verified](efficiency/VERIFICATION.md) on 2026-09-20. Empirical savings/adoption milestone: NJ-07 and NJ-11 evidenced, with NJ-08–10 explicitly dispositioned. This separation allows useful code to ship without fabricating live benchmark evidence.

## Sources

- R1: [RTK README](https://github.com/rtk-ai/rtk).
- R2: [RTK savings explanation](https://github.com/rtk-ai/rtk/blob/develop/docs/guide/resources/savings-explained.md).
- J1: [TypeSafe primitives](https://docs.typesafe.ai/introduction).
- J2: [LangChain evaluation](https://www.langchain.com/blog/jev-agent-evals-langsmith).
- J3: [Jev gateway](https://github.com/vinilana/jev-gateway).
- J4: [Browser Use Jev](https://github.com/browser-use/jev-ultrafast).
- Local design: [cost policy](NIGHTSHIFT-COST-POLICY.md), [run measurements](RUN-MEASUREMENTS.md), [efficiency roadmap](EFFICIENCY-ROADMAP.md).

Sources reviewed in the planning conversation on 2026-09-20; pin and reverify implementation-specific APIs and binaries before integration.
