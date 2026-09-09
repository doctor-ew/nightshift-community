# Risk-based behavioral proof before full implementation

Status: Recovery design approved by independent review 849fd60f2a934cd98bbf896b1b66db23. Runtime execution and final acceptance remain required.
Baseline: integration/nightshift at 44ad7cc4d6af7a30cde2b139d9ad25c19b41c2bf; issue 19 integrated.
Delivery: isolated integration PR. No active installation update, Coach changes, paid API fallback, main promotion or deployment.

## Problem

Relevant RED assertions catch deterministic defects, but agent/prompt work can proceed into surrounding implementation before anyone executes its risky behavioral assumptions. The current extractor verifies source claims and the GREEN architect returns files_changed; neither is a behavioral oracle. Introduce conditional proof without charging ordinary deterministic work for a universal model gate.

## Technical Constraints

Reuse the integrated project-context/convention resolver, existing role dispatcher and routing, existing retry accounting, and existing final review/drift/QA. Do not add a top-level stage, container prerequisite, arbitrary grader commands, BDD dependency, or independent retry engine. Exact provider flags belong only in the runner adapter. Unknown/unavailable required proof blocks. No required final evaluation is waived by absent Playwright.

New names and schemas below are proposed additions, not pre-existing APIs.

## Solution Design

### 1. One versioned scenario representation and explicit adoption

New canonical public artifact: `docs/<task-key>/behavior-scenarios.json`. New documentation: `docs/BEHAVIOR-PROOF.md`. Version 1 top-level keys: version, task, ac_ids, author, applicability, runtime, prototype_files, cases, heldout. Unknown keys/types and duplicate JSON keys reject input.

- author: provider and stable author_id, recorded by orchestration rather than accepted from prototype output.
- ac_ids: unique stable public AC IDs. Each case has a nonempty ac_ids list drawn from this set, allowing explicit many-to-many coverage. SPEC Test Plan maps IDs explicitly; do not infer stable IDs from reordered prose. Every AC requires at least one required case or explicit reviewed not_applicable case.
- applicability: a derived summary with kind, rationale, risks and review. kind is prototype if any required case is prototype, otherwise deterministic if any required case is deterministic, otherwise not_applicable. risks is the union of case risks; the summary cannot downgrade them. Per-case applicability uses the same keys. Finite risks are deterministic_logic, prompt_behavior, agent_behavior, runtime_interaction and safety_sensitive. Prompt/agent/runtime risks require prototype; safety_sensitive deterministic cases require independent design challenge but remain deterministic execution. not_applicable requires empty risks and an explicit documentation-only rationale.
- review: null until classification is reviewed, then an attestation with reviewer_provider, reviewer_author_id, decision (approve/repair), reviewed_input_sha256 and evidence_sha256. The trusted orchestrator records actual existing independent review provenance for deterministic/not_applicable classification; no extra model call is required just to produce this attestation. Reviewer identity must differ from the applicable author. Hash the canonical applicability/case semantics excluding review fields to avoid recursive hashes. Prototype/safety_sensitive classification additionally requires the typed challenge receipt described below. Missing review blocks seal/admission, not schema-only validate.
- runtime: null if no prototype cases; otherwise profile `claude-subscription-text-v1`, model, cli_version and system_prompt_file. Required other profiles yield unsupported/unknown. Tool/runtime interaction requiring more than no-tool single-turn text is not downgraded to this profile.
- prototype_files: exact repository-relative regular files permitted during early prompt development/repair, without wildcards, symlink escape or surrounding application scaffolding; empty when no prototype is applicable.
- cases: common public/private case schema with id, ac_ids, required (boolean), applicability, given, when, then, forbidden (a string containing the public forbidden-behavior description), input, expected, prohibited, counterexamples and visibility (public/held_out). Prototype cases require nonempty synthetic input and at least one positive expected oracle; an empty prohibited list requires explicit forbidden rationale. Only deterministic/not_applicable cases may use null input and empty expected/prohibited lists; their evidence comes from ordinary tests or reviewed rationale. Optional cases never satisfy required AC coverage or downgrade mandatory risks. IDs are unique across public/private sets.
- heldout: public manifests use null without prototype cases, otherwise manifest_sha256, case_ids, author (provider/author_id), prepared_at; no private body/path. Private manifests have the exact same top-level keys with heldout:null, avoiding a self-hash. The union of required private prototype case ac_ids must cover every required public prototype AC. Validate this union at seal when both manifests are available, not while validating the public marker alone.

Private manifests contain prototype cases only, all held_out. Their bodies remain outside checkout, worktrees and reachable project Git history. Fix them before prototype execution with author identity distinct from spec/prototype author. They may come from independently supplied synthetic fixtures without a universal fixture-author model call. Retain their locator only in the private canonical ledger. Hashes attest identity, not malicious-host access control.

Canonical product/spec authoring writes version-1 scenarios before approval; a missing artifact at new implementation admission blocks. Existing low-level state/context/manifest and legacy spec-lock helper APIs remain backward compatible. GREEN role dispatch deliberately adopts a stricter contract: engineer/architect calls require task-bound proof, including existing fixtures; there is no implicit legacy dispatch bypass. Existing manifests without behavior_proof get safe defaults; absence is not opt-out. A pre-existing spec lacking scenarios must be explicitly classified/migrated by the canonical stage before new GREEN work; do not grandfather it based on filename, old timestamp or absent config. Completed historical receipts remain historical and are not relabeled proof-passed. This version/adoption rule preserves legacy helper fixtures without silently exempting new stage runs.

### 2. Typed conditional independent challenge

New role: `agents/nightshift-behavior-reviewer.md`; new schema: `contracts/nightshift-behavior-reviewer.schema.json`. Extend the existing dispatcher role allowlist, typed failure-receipt mapping, jq role validator and routing for this role; leave existing architect/extractor schemas unchanged. Reuse the common status/reason/attempts/artifacts/rules_fired/results envelope. Proposed results keys: decision (approve or repair), scenario_ids (complete reviewed set), findings (objects with scenario_id, code, reason), and reviewed_input_sha256. SUCCESS means a valid review report; approval additionally requires decision=approve, complete scenario IDs, matching digest, no unresolved findings and actual distinct-provider reviewer provenance.

Architectural design guidance maps requirements to public expected/forbidden outcomes and counterexamples during existing specification work. The new reviewer challenges that design; it does not execute the prototype or claim proof from source existence. Prototype and safety_sensitive annotations require independent challenge; ordinary deterministic/documentation-only changes use existing review without this extra model invocation.

Proposed reviewer routes copy the current architect entries exactly: gears 1 and 2 use provider claude/model sonnet; gears 3 and 4 use provider claude/model opus. Keep the reviewer read-only and use existing cross-provider adversarial selection with actual author-provider provenance; do not change existing architect routes. The runner reserves the call before invoking the existing dispatcher directly, not the extractor-only bounded-dispatch wrapper. One challenge dispatch is one counted call; no hidden alternate/retry launch. Provider failure returns unknown and consumes infrastructure allowance. Never map extractor VERIFIED or reviewer confidence to behavioral pass.

### 3. CLI, sealed data and authoritative receipt

New stdlib helper: `scripts/nightshift-behavior-proof.py`.

Shared arguments: `--project DIR --task TASK` (task is unnecessary only for `validate --config-only`); validate TASK against existing safe task conventions and reject path traversal. Resolve physical project with scripts/nightshift-project-context.py. Read the canonical manifest with existing precedence and tomllib. All CLI output is one sanitized JSON object. Exit 0 means the requested operation succeeded; gate additionally requires eligible evidence. Exit 1 means blocked/failed/unknown; exit 64 means malformed arguments/config/schema. Human text, raw provider output, credentials and private locators do not appear in CLI diagnostics.

| Operation | Proposed arguments and effect |
| --- | --- |
| validate | `--scenarios FILE`; read-only schema, AC coverage, applicability, path and config validation. `--config-only` validates optional policy without requiring task/scenarios and is used by manifest validation |
| challenge | `--scenarios FILE --out FILE`; reserve a canonical development call, invoke typed independent reviewer, persist transport-owned provenance and report; evaluate approval locally |
| seal | `--scenarios FILE --challenge FILE --heldout FILE`; validate approval when required and independently authored private holdout; atomically bind SPEC, public/private scenario, scope, runtime, oracle-version and current prototype hashes |
| record-red | `--evidence FILE`; ingest trusted structured evidence from the existing RED execution, with selected exact command/source, actual nonzero exit, explicit scenario coverage, relevant assertion failures, retained log/test hashes, independent observer provider/author_id and red-lock SHA; the trusted orchestrator records observation and semantic relevance; model SUCCESS is never RED evidence and no supplied command is executed |
| record-final | `--evidence FILE`; ingest actual ordinary final-test success with zero exit, required deterministic scenario coverage, retained log/test hashes, independent observer provenance and final source hashes; no command execution and no expected-RED reuse |
| run | `--gate development|final`; run required prototype cases only (public in development, held_out in final), not yet accepted for current hashes, one bounded provider launch per case, followed by deterministic local oracle; no arbitrary output override or runner command |
| gate | `--gate development|final`; read-only hash/coverage/challenge/evidence validation returning pass/fail/unknown and next action |
| status | read-only canonical ledger summary with counters and sanitized latest receipt |

Internal version-1 proof receipt includes task, gate, outcome (pass/fail/unknown), applicability/rationale, scenario IDs, input/seal/prompt/oracle/runtime/policy hashes, challenge identity, actual attempt identities, expected_red_observed when relevant, timestamps, observed duration/token counts, distinct failed scenario IDs, evidence digests, counters and fixed next_action. not_applicable is applicability, not a fourth execution outcome. Deterministic observed failure is not relabeled behavior pass; it is explicitly sufficient development admission evidence. Existing final test success recorded through record-final remains necessary for deterministic cases; expected_red_observed can satisfy development admission only, never the final gate. not_applicable cases require the reviewed rationale at both gates. Mixed tasks aggregate required evidence per case: prototype completions, deterministic RED/final-test observations and not_applicable attestations.

Store authoritative receipts and ledger under `<git-common-dir>/nightshift/behavior-proof/<task>/`; common-dir discovery makes worktree spelling and report path irrelevant. Non-Git projects cannot establish this durable proof identity and return unknown before model launch. Separate development/final counters share one task record; changing scenario/spec/output paths never erases reservations or raises limits. Use existing scripts/nightshift-retry-budget.py account locking/atomic writes with optional explicit pinned limits; unchanged callers retain existing limits and behavior. Add a reserve/finalize API only as needed within that helper, not a copied engine. Pin effective policy on first reservation and reject changed limits during that task without an explicit reviewed migration retaining counters.

The development seal binds spec/scenario/oracle/runtime/scope/challenge and locked-test hashes, plus prototype revisions. It does not bind surrounding production contents before GREEN: legitimate scoped implementation must not invalidate development admission merely by creating/changing those files. The final gate binds the final content hashes of all task Files-to-Change source/test artifacts except docs/<task>/ delivery evidence, plus current prototype/spec/scenario/oracle/runtime hashes. Missing declared final files block. A scope violation or changed locked tests/oracle/spec always invalidates proof; ordinary allowed surrounding GREEN edits only invalidate prior final evidence, not development admission. Initial prototype text hashes are sealed. Up to two permitted repairs may change only prototype_files and create new linked revisions with retained original seal, changed text hashes and consumed counters; they never mutate expected/prohibited assertions, holdout or scope. Outside-scope changes, runtime/oracle/spec changes or missing hashes make prior proof stale and block admission pending re-challenge/reseal; counters remain. New current prototype hashes must have accepted evidence before GREEN and final completion.

Extend spec-lock only when the versioned artifact exists: stage explicit public scenario/seal references together with SPEC, check staging failures, and prevent unrelated pre-staged files from entering the seal commit. Private case bodies never enter Git. Existing callers without scenarios retain their legacy helper contract, while canonical stage admission enforces adoption above.

### 4. Real bounded subscription prototype and deterministic oracle

Supported profile is one task-system-prompt plus one synthetic user input, no model tools, no resume/session history. The runner constructs an argv array using locally verified Claude controls: safe mode, empty tools, no session persistence, print mode, JSON transport and explicit model/system prompt. Execute in an empty private temporary working directory. Do not use the existing Nightshift role wrapper for the prototype: its injected status schema changes the behavior under test. Do not use bare mode, which disables OAuth authentication. Preserve admin-managed policy; inability to establish the profile blocks.

Strip exactly the current dispatcher subscription billing/proxy environment variables and verify the existing Claude subscription auth JSON predicate before launch. Do not copy auth stores, read token values or add API fallback. Record executable identity/version and configured model; record reported model when present and explicit alias limitation otherwise. Required CLI/version/profile mismatch yields unknown rather than silently selecting another runtime.

Use process-group launch, bounded output pipe consumption, timeout and terminate/grace/kill/reap cleanup. Bound combined captured stdout/stderr to configured output_bytes without unbounded communicate buffering. Timeout, output quota or unconfirmed cleanup produces infrastructure unknown. The model gets no local tool or code execution channel; raw completion is data, never shell, import or callback. Envelope completion text is extracted separately from any provider status field, then evaluated by trusted local assertions. Provider SUCCESS or zero exit is insufficient.

Proposed built-in oracle version 1 supports only text_equals, text_contains, json_equals and json_field_equals. Each assertion is a typed object with op and value; json_field_equals additionally has a field path represented as a list of literal object keys, with no indexing expression/eval. Reject duplicate JSON keys, nonfinite values, unsupported operations and wrong types. JSON comparisons preserve type distinctions (boolean is not integer). expected assertions must all hold; prohibited assertions must all be false. Unparseable response for a required JSON oracle is observed wrong behavior (fail), while missing completion/transport/schema failure is unknown. Return failed scenario IDs and sanitized reason codes; do not echo private expectations or raw completion to implementation workers.

Held-out final evaluation runs only after development admission and final prompt hash is fixed. No automatic substantive final repair from hidden output. If a held-out case informs repair, mark exposure, block fresh-validation claims and require independently authored replacement heldout plus re-challenge/reseal, retaining all counters. Existing prompt-only context filtering is not protection against arbitrary malicious host processes; the supported no-tool/no-customization profile and tested input boundaries are the runtime containment claim.

### 5. Finite policy, final gates and metrics

New optional `[behavior_proof]` keys and defaults, supplied by the proof helper when absent without forcing setup to materialize them: version=1, development_calls=8, final_calls=2, repairs=2, infrastructure_failures=2, timeout_seconds=120, output_bytes=1048576, force_prompt=false. force_prompt must be boolean and may strengthen applicability to prototype only; false cannot lower required prompt/agent/runtime proof. Reject booleans as integers, invalid/nonfinite values, unknown keys and unsupported version. Calls may be configured within 1..64 per gate, repairs within 0..2, infrastructure_failures within 0..2, timeout_seconds within 1..120 and output_bytes within 1..1048576. force_prompt cannot turn deterministic test evidence into an LLM assertion substitute: when enabled, add reviewed prototype coverage for affected ACs while retaining required deterministic cases, or block if no supported profile exists. Lower caps may block earlier but never skip mandatory proof. No disable flag or arbitrary runtime command. Mandatory applicability is enforced independently of config.

Count each actual challenge/provider case launch once. A three-case suite costs three launches, not one. Initial dev suite plus up to two prompt revisions share eight launches; challenge/re-challenge and infrastructure retry also consume that cap. Final prototype cases/retries share two launches; deterministic final evidence consumes no model call. Admission rejects a case set whose minimum calls exceed remaining cap before starting it; no partial success can mask unexecuted required cases. Infrastructure failures also increment the task's infrastructure ceiling. No separate model-repair dispatch feature: orchestration makes the smallest allowed prompt edit using its existing workflow, recorded as at most two substantive revisions. No hidden proof worker/model launch is permitted outside ledger accounting. Authenticate/version probes are not provider model calls and do not fabricate token observations.

Enforce development admission in scripts/nightshift-agent.sh before any engineer/architect authentication/model provider launch, not merely in stage prose. Add mandatory `--task TASK` for these two roles; resolve project with existing neutral context, call the proof helper's development gate, and block missing/unknown/stale evidence. Other roles keep their task-optional contract; the independent reviewer must remain callable before proof exists. No bypass flag, environment exemption, role-child exemption or legacy-fixture loophole. Preserve existing scope activation before prototype work; scope activation is not GREEN admission.

The canonical GREEN callsite in commands/nightshift-implement.md must pass `--task "$TASK"`. The engineer call in scripts/nightshift-trajectory.py must establish an admissible synthetic task and pass its task ID. Existing tests/test-agent-dispatch.sh engineer/architect fixtures and tests/test-run-metrics.sh deliberately create reviewed deterministic/not_applicable task evidence and pass task IDs; they must not change the role to evade the gate. Missing-artifact and unknown-required-proof cases must show zero provider calls. tests/test-factory-auth.sh only invokes an argument-less role-child recursion guard; that existing pre-parser rejection remains unchanged. Product/spec calls dispatch spec-writer/extractor and need no GREEN admission change. The bounded retry dispatcher is extractor-only. Record this intentional role API migration in documentation.

Place development gate immediately before GREEN in commands/nightshift-implement.md as the user-visible stage explanation as well. Deterministic work reuses Step 5 relevant RED and red-lock once. Prompt work permits only the sealed prototype exception before development pass, not surrounding production artifacts. Place required final gate in commands/nightshift-qa.md before APPROVE, including no-Playwright cases, and require successful final gate in the canonical orchestrator before completion. Keep ordinary review/drift/tests intact.

Record elapsed time, observed usage and distinct failed scenario IDs in proof receipts; unknown usage remains null. Reuse current run identity and optional metrics observation event with existing implement/adversarial stages. Add the new reviewer role to metrics allowlist. Do not add arbitrary prompt/content fields or invent an aggregate defect metric; proof receipts hold the observed distinct defect count. Metrics failure never changes proof outcome.

### 6. Issue 13 bootstrap before broad implementation

The runner is incomplete and has not established the required proof. The retained premature implementation attempts do not satisfy the originally required order (see Recovery amendment below). Before further surrounding engine/config/stage changes: approve the recovery design through independent cross-provider challenge, then allow a narrowly scoped manual prototype comprising only the new reviewer role prompt, its strict schema, and synthetic development/held-out case artifacts. Record this explicit exception as bootstrap evidence, not as a fabricated runner receipt or a legacy exemption.

Use the verified no-tool Claude subscription CLI directly through a local bounded process wrapper outside the worktree. An independent reviewer fixes public expected/forbidden assertions and separately retains heldout before execution. Run a synthetic design-review task whose machine oracle rejects an approving answer when a required negative case is absent, then accepts a corrected design and checks an independently prepared heldout. Review the bootstrap prompt and oracle before calls. Record real versions, hashes, provenance, output digests, durations and counters, with no self-reported verdict accepted. Maximum bootstrap calls development 8/final 2, including counted design challenge calls relevant to this bootstrap. Retain the manual bootstrap ledger immutably outside the checkout and link its digest from issue 13 delivery receipts. Do not import historical attempts through a production API, merge counters with later helper fixture tasks, or claim the helper executed them. This self-hosting exception applies only to issue 13 manual delivery evidence; it introduces no reusable runtime bypass flag.

Only after accepted bootstrap behavior proceed to engine implementation under meaningful RED. After integration, repeat real supported-profile acceptance through the implemented helper in a separately identified synthetic fixture task; this establishes runner execution rather than only manual transport. Preserve the bootstrap record as distinct evidence. Neither experiment touches Coach, active runtime installs or production data.

## Recovery amendment — independently approved

The retained commits d2929e9, 45bfecb, 2c51e26 and 8dfc146 preceded approved specification and RED seals. They are incomplete implementation attempts, not accepted proof that original ordering complied. Preserve their history, budgets and the qualification in docs/13/recovery.md. A new seal cannot repair historical chronology, and earlier schema/missing-task checks are not complete behavioral verification.

The prospective recovery sequence is independent review of this amended specification and public scenarios; independent retained heldout commitment; expanded meaningful RED and recorded seals; approved narrow manual reviewer-prompt prototype; then further engine integration and actual implemented-runner verification. No new engine work is authorized by merely writing this amendment. Retain pre-existing source changes as explicit recovery baseline without treating them as admitted implementation. Existing accepted-source, scope, independent challenge and final evidence requirements remain.

The public scenario artifact maps AC-1 through AC-9 to the numbered criteria below. Cases 13-admission through 13-recovery-and-delivery cover local deterministic claims; 13-reviewer-missing-negative and 13-reviewer-complete-design are the only prototype cases, covering AC-2/AC-3/AC-9. They test the new reviewer prompt's actual output, not a claim that text runtime proves accounting, filesystem isolation or configuration correctness. Private commitment metadata covers the same prototype AC union; the author of this public artifact has not read the private bodies. Classification review fields remain null until actual independently approved evidence is recorded. The runtime records the currently verified Claude CLI 2.1.265; no prior 2.1.263 observation is represented as evidence for the newer binary.

## Acceptance Criteria

1. New canonical specs produce versioned per-case scenarios with explicit many-to-many AC coverage; direct engineer/architect dispatch without task-bound accepted proof launches no provider; missing/malformed/unresolved AC/oracle/runtime inputs block applicable admission. Legacy low-level helper fixtures remain compatible without granting missing-artifact bypass to new stages.
2. Ordinary deterministic tasks use the same relevant RED execution and no additional model call. Typed independent review precedes risky proof; same-author provider or wrong digest/incomplete review blocks.
3. Real supported no-tool subscription prototype completion is evaluated by local text/JSON assertions. Wrong/forbidden behavior fails; unavailable runtime, transport failure and missing evidence are unknown. No provider self-report grants approval.
4. Only declared prototype text changes before development pass; up to two repair revisions retain oracle/scope/holdout and counters. Stale input hashes block. No broad GREEN work before admission.
5. Canonical task/gate reservations are atomic, output-path independent, resumable and idempotent. Count calls per case and reviewer launch; pending/exhausted limits block without reset on changed paths/hash. Existing retry defaults remain unchanged.
6. Heldout remains outside checkout/history and model context except each input; final pass is required despite no Playwright. Exposure requires new independent cases and invalidates prior freshness.
7. Deadline/output bound kills/reaps process groups and emits unknown on interruption. Billing credentials are stripped per existing policy; no fallback or configuration mutation. CLI/profile version evidence is honest.
8. Safe defaults and bounded config validation preserve existing manifest precedence/setup behavior. Optional metrics record observed duration/tokens/defects or null; no sensitive content enters metrics.
9. Under the explicitly documented recovery amendment, independent challenge and real narrow prototype pass precede further broad implementation; retain the earlier ordering failure without claiming original compliance. The completed helper later passes a real supported-profile acceptance, plus offline privacy/concurrency/invalid-input fixtures and existing regressions.

## Files to Change

| File | Change | Why |
| --- | --- | --- |
| scripts/nightshift-behavior-proof.py | [NEW] CREATE | Versioned validation, runner, oracle, seal and gate |
| scripts/nightshift-install-inventory.py | MODIFY | Shared proof documentation mapping and legacy helper dependency closure |
| agents/nightshift-behavior-reviewer.md | [NEW] CREATE | Typed independent design challenge |
| contracts/nightshift-behavior-reviewer.schema.json | [NEW] CREATE | Strict reviewer result |
| scripts/nightshift-agent.sh | MODIFY | Admit reviewer; mandatory task-bound engineer/architect gate before provider launch |
| scripts/nightshift-trajectory.py | MODIFY | Supply admissible synthetic task to existing engineer dispatch |
| scripts/nightshift-contract.jq | MODIFY | Validate new role result |
| scripts/nightshift-retry-budget.py | MODIFY | Optional pinned proof limits/reservation reuse |
| scripts/nightshift-tdd-spec-lock.sh | MODIFY | Explicit public proof sealing when adopted |
| scripts/nightshift-manifest-validate.sh | MODIFY | Validate optional proof policy |
| scripts/nightshift-run-metrics.py | MODIFY | Allow new reviewer observation role |
| routing.json | MODIFY | Explicit reviewer routes without changing existing roles |
| nightshift.toml | MODIFY | Document finite defaults |
| agents/nightshift-spec-writer.md | MODIFY | Author versioned scenario artifact and references |
| commands/nightshift-product.md | MODIFY | Scenario/design preparation before approval |
| commands/nightshift-spec.md | MODIFY | Adopt scenario artifact and conditional challenge |
| commands/nightshift-implement.md | MODIFY | Development admission and bounded prototype exception |
| commands/nightshift-qa.md | MODIFY | Required final proof independent of browser skip |
| commands/nightshift-eng.md | MODIFY | Preserve stage completion gate on proof result |
| scripts/nightshift-branding-policy.json | MODIFY | Exact reviewed adapter contexts only if scanner finds new legitimate matches |
| docs/BEHAVIOR-PROOF.md | [NEW] CREATE | Contracts, adoption, limits and unsupported profiles |
| docs/CONFIGURATION.md | MODIFY | Validated proof settings |
| tests/test-agent-dispatch.sh | TEST | Explicit valid task admission for existing GREEN fixtures; missing/unknown proof blocks calls |
| tests/test-run-metrics.sh | TEST | Task-bound deterministic fixture for role observations |
| tests/test-behavior-proof.sh | [NEW] TEST | Focused semantic, privacy, budget and adoption regressions |
| tests/nightshift-behavior-fixture.py | [NEW] TEST | Shared test-only normal admission fixture; no runtime bypass |
| docs/13/SPEC.md | CREATE | Reviewed implementation specification |
| docs/13/behavior-scenarios.json | [NEW] CREATE | Public issue 13 scenarios and bootstrap scope |

The shared inventory already discovers prefixed Python helpers for the shared runtime, role Markdown and contract schemas. Extend only scripts/nightshift-install-inventory.py with these proposed exact mappings; install.sh and scanner consume that single definition:

| Source | Destination | Category/runtime |
| --- | --- | --- |
| docs/BEHAVIOR-PROOF.md | Nightshift target docs/nightshift-behavior-proof.md | shared, every runtime |
| scripts/nightshift-behavior-proof.py | Claude target scripts/nightshift-behavior-proof.py | claude_adapters, claude/all |
| scripts/nightshift-retry-budget.py | Claude target scripts/nightshift-retry-budget.py | claude_adapters, claude/all |

The existing legacy project-context.py mapping remains. The adopted legacy agent/spec-lock shell helpers resolve the proof helper adjacent to themselves; proof imports adjacent retry accounting with bytecode writes disabled. These explicit legacy mappings close that dependency without copying all shared Python helpers. Metrics remains optional: if the adjacent metrics helper is absent, retain proof-local observed values and unavailable linkage; do not require or copy metrics merely for GREEN admission. Role/stage instructions reference docs/BEHAVIOR-PROOF.md in source and its prefixed shared installed documentation path. Do not duplicate destination rules in install.sh/scanner, and do not repair unrelated legacy routing naming in this issue. Private fixtures and canonical runtime ledger are not committed. Stage receipts under docs/13 are evidence, not production scope expansion.

## Test Plan

Author relevant failing assertions against schema/admission/ledger/oracle behavior, not only missing imports. Test malformed/duplicate schemas, missing AC coverage, unsupported profile, stale seal, same-provider reviewer, pending reservation, canonical identity across worktrees/output paths, concurrent finalization, per-case limits, two-repair exhaustion, unknown/final-skip rejection, holdout exposure, no-tool argv and inherited customization exclusion, child cleanup, byte caps, no secrets in output/metrics, and unchanged existing retry/account callers. Validate copy/symlink installed helper/role/schema/documentation availability and legacy adjacent proof/retry dependency closure through issue 19 inventory and branding guard, including proof success with optional metrics helper absent. Run shellcheck and existing offline harness after focused tests; record environment-required escalation separately. Real bootstrap and completed-runner subscription acceptance are additional evidence, never inferred from provider stubs.

## Risks and Open Questions

- The no-tool CLI controls are supported by the locally inspected Claude version, but combined safe-mode/tool suppression and output envelope semantics must be established by bootstrap. If unsupported or admin policy conflicts, stop applicable proof rather than invent control flags.
- Trusted record-red ingestion requires the canonical orchestrator to supply genuine retained test evidence. The helper cannot establish arbitrary assertion relevance from prose or prevent a malicious same-user host from forging receipts; document this authority boundary explicitly.
- Eight development/two final calls cap case volume. A task with more required cases must explicitly configure a larger finite reviewed cap or block; this is not permission to silently sample fewer cases.

## Model Router

Decision: nightshift-architect. The feature changes cross-module admission, runner/accounting and typed contracts. Spec author: codex. Independent cross-provider challenge must precede the narrowly authorized bootstrap; existing role routing remains authoritative. No static provider/model key belongs in the new role prompt.

## Sources

Repository citations below refer to integration/nightshift at 44ad7cc4d6af7a30cde2b139d9ad25c19b41c2bf.

- https://github.com/doctor-ew/nightshift-community/issues/13 — early real proof, independent challenge, heldout, budgets, metrics and delivery limits; read 2026-09-08.
- agents/nightshift-spec-writer.md:68-101 — current Given/When/Then template and required spec sections.
- docs/PROJECT-CONTEXT.md:1-75 — integrated neutral context and convention contracts.
- commands/nightshift-implement.md:178-196,215-262 — relevant RED, test firewall, sealing and GREEN dispatch.
- scripts/nightshift-tdd-spec-lock.sh:16-37 — existing SPEC-only staging and lock recording.
- scripts/nightshift-trajectory.py:163-171; tests/test-run-metrics.sh:26; tests/test-agent-dispatch.sh:78-80,183-203,236 — actual GREEN dispatch consumers requiring explicit fixture/task migration.
- routing.json:124-145 — exact architect gear entries copied for the proposed reviewer.
- scripts/nightshift-agent.sh:135-175,185-228 — role allowlist, configured routing/subscription boundary, role wrapper and process launch.
- scripts/nightshift-agent.sh:81-119 — current process-group interruption cleanup.
- scripts/nightshift-contract.jq:5-27; contracts/nightshift-architect.schema.json:49-63 — strict current role shapes.
- scripts/nightshift-retry-budget.py:15-54,57-131 — atomic accounting and current extractor/output-directory limitations.
- scripts/nightshift-controller.sh:28-42,72-108 — existing gate allowlist and different attempt semantics; not reused as a new proof stage.
- commands/nightshift-qa.md:77-82 — existing no-Playwright approval.
- scripts/nightshift-manifest-validate.sh:12-33; scripts/nightshift-setup.py:34-40 — existing policy validation/defaults, no proof settings.
- scripts/nightshift-run-metrics.py:46-57,450-481 — role/stage allowlists and typed event CLI.
- scripts/nightshift-install-inventory.py:85-110 — shared prefixed helper/role/schema mappings, shared project-context documentation, and the existing legacy project-context helper mapping.
- Local authoritative CLI lookups: claude --help / --version (2.1.263) and codex exec --help / --version (0.153.4), read 2026-09-08 — verified Claude safe-mode/tools/session controls; no verified all-tools-off Codex profile claimed.
- origin/docs/13-behavioral-proof-design:docs/13/DESIGN.md — retained proposal, used as design context rather than implemented API evidence.

## Normative protocol details

These proposed details resolve the fixture/implementation interface before sealing.

### Review digest and visibility

Applicability kind is derived from required cases only. Summary risks is the union of all public case risks, including optional cases. Per-case risk rules apply to every case. Runtime metadata is required if any public case is prototype, including optional prototypes. An optional prototype case may supplement coverage only when its AC IDs already have required prototype coverage; otherwise validation rejects the document. This prevents optional labeling from suppressing required execution. Only required cases are executed for admission; optional cases never satisfy coverage. A safety-sensitive risk anywhere requires the typed independent challenge.

Canonical JSON is UTF-8 json.dumps with sort_keys=True, separators=(",", ":"), ensure_ascii=False and allow_nan=False. All input parsing rejects duplicate keys and nonfinite numbers. The review input digest hashes the complete public scenario manifest after replacing only its top-level applicability.review and each case.applicability.review with null. Do not recursively remove arbitrary data keys named review from oracle values or synthetic inputs. Every classification attestation references that same digest. Attestations are trusted orchestration records of existing review, not a cryptographic claim that an arbitrary local JSON author is independent. Their evidence_sha256 is the recorded digest of the actual retained review evidence. Validate 64 lowercase hex digests and distinct (provider, author_id) identity; typed prototype challenge additionally requires distinct provider.

The typed challenge receives public cases and public heldout commitments only. Its scenario_ids must exactly cover public case IDs; private bodies/locators are not supplied as review input; commitment case IDs are public metadata, not reviewed public cases. Private classification attestations reference the corresponding private manifest semantics digest, with the same serialization. Validate heldout author identity against public author and match the public commitment exactly. Review roles receive sanitized materialized inputs, never private file locators.

### Trusted ordinary test evidence

record-red and record-final accept exactly these version-1 JSON keys: version, task, gate, observer, scenario_ids, command, exit_code, assertions, log, tests, red_lock_sha, source_hashes.

- gate is development for record-red, final for record-final. observer has exactly provider and author_id and differs from the scenario author identity. scenario_ids is a nonempty unique list of required deterministic public cases; complete required deterministic coverage is needed for the corresponding gate.
- command has exactly argv and source. argv is a nonempty array of nonempty strings retained as data and never executed by the proof helper. source has exactly path, line and sha256: an existing confined repository-relative regular file, positive integer line and its actual content digest. The canonical orchestrator verifies the selected command against the applicable project convention/configuration source before recording it.
- exit_code is an integer (not boolean) in 1..255 for RED and exactly 0 for final. assertions has exactly kind, passed and failed: kind is relevant_assertion; counts are nonnegative integers; RED requires failed >= 1; final requires failed == 0 and passed >= 1. Missing imports/tools, schema rejection or provider SUCCESS alone are not relevant assertion evidence.
- log has exactly path and sha256. The path is an explicitly supplied absolute retained regular log file; reject symlinks and oversized logs rather than following arbitrary links. The helper hashes this requested file without echoing its contents or path. The observer is trusted to attest the real execution and semantic relevance; file hashes establish integrity, not authenticity against a malicious same-user host.
- tests is a nonempty array of objects with exactly path and sha256, confined repository-relative regular test files. Every digest must match current bytes and the seal's locked test set. red_lock_sha is the full Git commit SHA corresponding to the existing task RED lock; verify it resolves to that recorded lock and binds these test files. Tests do not change between RED and final success; implementation changes make the same assertions pass.
- source_hashes is an empty object for RED. For final it maps every declared final source/test path (excluding docs/task delivery evidence) to its current SHA256; missing/extra/mismatched entries reject evidence. The helper validates these snapshots independently rather than accepting caller hashes without reads.

Retained log reads are bounded at 4 MiB; scenario/evidence/config JSON inputs at 1 MiB. Hash repository source/test artifacts by streaming bytes rather than imposing the prompt-output cap on arbitrary source assets. Fixed diagnostics never print command argv, log locators, source content or observer-supplied messages. Record actual observations through the trusted orchestrator; the helper does not claim to reconstruct execution from a report.

### Scope and lifecycle

Seal reads the exact Files-to-Change table and records the current repository baseline, including existing tracked/untracked changes. Preserve pre-existing dirty files as baseline data; do not adopt unreceipted implementation ownership. Compare subsequent changes against this snapshot, not against an assumed clean index. Runtime state, Git metadata and docs/task delivery receipts are excluded from broad change detection; SPEC and scenarios remain independently bound despite their task-directory location. Declared prototype files must exist at seal. Declared surrounding source files may be absent until GREEN; record absence explicitly and require all declared final files at final evaluation.

Before the first development pass, only declared prototype files may change from the sealed source baseline; locked tests remain unchanged and task evidence may grow. Detect premature surrounding source edits before executing another prototype or admitting GREEN. After the first accepted development pass, normal declared surrounding changes become allowed and do not stale development admission. They invalidate final evidence. New/modified out-of-scope source files always block; unchanged pre-existing dirty files do not become permission to edit them. A prototype revision after an observed behavioral failure is required before another substantive development run; repeated sampling of an unchanged failing prompt cannot manufacture a pass.

Spec-lock stages SPEC and the public scenario artifact when present. Runtime proof sealing follows RED-lock and writes private canonical state; its sanitized public receipt may be retained in docs/task afterward. Do not require a runtime seal to exist before the tests that it binds have been locked.

### Atomic accounting and exposure

Extend the existing retry module with a proof-aware operation under its existing locking/atomic-write primitive: one canonical task record contains pinned policy, attempt-to-gate metadata, development/final reservation counters and a task-wide infrastructure counter. Legacy account callers retain their exact interface/defaults. Do not implement separate competing budget files that permit cross-gate infrastructure races. Factor shared transaction mechanics rather than duplicating a retry engine.

Reservation ceilings conservatively include an unresolved pre-launch reservation. Record confirmed launches separately; a crash between reservation and launch must remain unknown/pending and cannot mint a replacement slot. Auth/version/profile admission occurs before a model reservation; a failed probe records an infrastructure observation without claiming a model launch. Probe failures still obey the same task-wide infrastructure ceiling. With infrastructure_failures=0, initial successful work is permitted and the first infrastructure failure forbids any retry; zero never blocks the initial attempt solely because counters start at zero. All counter transitions and idempotent finalization occur under the same task accounting lock. Gate/status reads never consume attempts.

Add expose --case ID as an explicit operation recording known private-case disclosure, with no hidden text in its output. Exposure invalidates final freshness. Replacing cases requires new independent commitments and challenge/seal with retained budgets; no automatic substantive final repair or unlimited replacement budget is added. An exhausted task stops with a concrete retained receipt.

Exposure reporting is a trusted-orchestrator obligation. The helper cannot detect undisclosed same-user access to private material or compel the orchestrator to call expose. Its freshness claim is conditional on honest exposure reporting, just as ordinary test observation relies on honest execution provenance.

### Snapshot and read-only details

Enumerate tracked files plus non-ignored untracked files using Git's NUL-delimited inventory. Independently include every explicit declared path even if ignored. Exclude Git metadata, .nightshift runtime state, local .nightshift.toml runtime configuration and docs/task delivery evidence from broad source-change snapshots; explicit declared paths override those exclusions, and SPEC/scenarios/effective policy remain independently bound. Use safe regular-file/symlink checks and streamed content hashes. Do not silently drop an unreadable inventoried source file.

A task without required deterministic cases needs neither ordinary RED evidence nor a RED-lock commit. This includes reviewed not_applicable-only and pure prototype tasks. Its sealed ordinary test set is empty and RED-lock identity null; reviewed classification, spec lock, source scope and required final-file checks still apply. Pure prototype tasks additionally require accepted development executions and independent heldout final evaluation. Required deterministic cases require the recorded RED lock and actual RED/final observations. Read-only gate/status must resolve existing task state without --create and read the sidecar directly; they must not invoke nightshift-lock-field.sh's mutating getter. Canonical ledger/lock paths reject symlinks below the verified Git common directory before mutation.

The test-behavior-proof.sh and shared test fixture helper are new relative to the cited baseline. They may exist as concurrent untracked RED drafts during review; verify baseline membership from the baseline Git tree, not a working-directory listing or an earlier git-status snapshot.
