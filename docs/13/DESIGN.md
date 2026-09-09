# #13 — Risk-based behavioral proof before full implementation

Status: **design proposal only**. No implementation, provider execution, proof result,
stage approval, installed-runtime update, or deployment is represented here.
Upstream: [community issue #13](https://github.com/doctor-ew/nightshift-community/issues/13).
Inspected baseline: `integration/nightshift` at
`bea0b3935f03a10e3c50b9db391039e1d85d76ad`. Paths and line numbers in Works Cited
refer to that commit, not a promise about a later checkout.

## Decision and boundaries

Propose one canonical scenario artifact, reused by specification, early proof,
ordinary RED tests and final verification. Do not add a universal BDD agent,
Cucumber dependency, new top-level pipeline stage, second test author, or model
invocation for formatting. Existing specification ACs already use Given/When/Then;
existing implementation already requires relevant RED assertions and test sealing
[S1, S2]. These are integration points, not features to rebuild.

Design can proceed alongside #8; implementation follows #18's convention/capability
contract. Optional metrics must not block proof when #8 is absent. This proposal
does not touch Idea Coach or use it as a live experiment. Scope is Nightshift only.
Sequence and delivery restrictions come from the upstream issues [U1–U4].

## One scenario representation — proposed, not implemented

Propose `docs/<task-key>/behavior-scenarios.json` as the single versioned source of
scenario semantics. SPEC.md's Test Plan references scenario IDs and a content hash;
any readable table is generated from that artifact, never maintained separately.
Each scenario has the following proposed fields (none are existing CLI/config APIs):

| Field | Meaning and validation rule |
|---|---|
| `id`, `ac_id` | Stable unique scenario ID and an existing spec AC reference. Missing/duplicate/unresolved references reject admission. |
| `given` | Public preconditions and synthetic fixture reference; explicit unavailable-resource conditions when relevant. |
| `when` | One observable action or bounded interaction sequence. |
| `then` | Observable expected outcome, not subjective confidence or “works correctly.” |
| `forbidden` | Forbidden observable outcome(s), including negative assertions. Empty list needs applicability rationale. |
| `counterexamples` | Boundary/adversarial examples that could falsify the design; reference fixtures rather than duplicate their content. |
| `oracle` | Registered deterministic assertion/rubric identifier and version/hash; never executable shell copied from a model response. |
| `evidence` | Required evidence kind and relative artifact reference; actual output/digest lives in the separate execution receipt. |
| `applicability` | `deterministic`, `prototype`, or `not_applicable`, with requirement-linked risk reasons and explicit rationale. |
| `visibility` | `public` or `held_out`; held-out fixture bodies are stored separately with the same scenario schema. |

The same schema serves public and held-out manifests; they are not two competing
scenario formats. Public ACs, expected behavior and forbidden behavior remain
available to implementers. Exact held-out fixtures, assertions and tester output
do not. Existing implementation firewall constraints must remain intact [S2, S3].
Hashes establish identity, not hidden-data access control; enforcement requires
the existing context filtering plus a tested runner boundary, not a secrecy claim.

## Applicability and low-overhead admission

Proposed rule evaluation is deterministic over reviewed risk annotations; it does
not need an LLM router call. An independent reviewer challenges the annotations
when the risky path applies, rather than letting a worker label itself low risk.

| Change | Required early evidence | Admission consequence |
|---|---|---|
| Ordinary deterministic logic/contract | Existing focused RED/contract tests, tagged with scenario/AC IDs | Relevant RED permits GREEN; it is evidence the test detects the missing behavior, not a “behavior passed” claim. |
| Agent/prompt behavior or uncertain runtime-dependent interaction | Reviewed scenarios plus a minimal, allowlisted prototype on the intended runtime | Expected and forbidden outcomes must pass before surrounding production artifacts are built. |
| Safety-sensitive deterministic behavior | Focused negative/contract cases and independent design challenge | Deterministic execution is preferred; risk does not automatically imply an LLM test. |
| Documentation/no executable behavior | Explicit reviewed `not_applicable` rationale tied to changed ACs | No prototype call; existing review/drift still apply. |
| Missing runtime, evidence, applicability or oracle | Receipt with `unknown` and reason | Required proof blocks full implementation; no silent skip/pass. |

No promise of zero elapsed overhead: the aim is to replace redundant planning and
catch costly mistakes earlier. Whether it saves time/tokens is measured, not
assumed [U1, U2]. A tiny change with adequate deterministic evidence must not pay
for a generic multi-agent behavioral ceremony.

## Placement and ownership

1. **Product/spec preparation:** the architectural design function maps risky
   requirements to expected/forbidden outcomes and counterexamples, alongside
   the existing AC/Test Plan authoring. Capture actual author provenance. A
   focused design invocation is conditional on risk, not required for every ticket.
2. **Independent design challenge:** before proof execution, challenge requirements,
   applicability, oracle quality, negative cases and prototype scope in the existing
   adversarial phase. Retain findings and author/reviewer provenance. Do not confuse
   “identifier exists” with “design is correct”; current extractor claims only support
   VERIFIED/NOT_FOUND/CONFLICT, not a design-review verdict [S5, S6].
3. **Seal inputs:** extend the existing spec-lock boundary to bind scenario hash,
   selected prototype scope, runtime requirement and oracle version. Current helper
   explicitly stages SPEC.md only; additional artifacts are a required implementation
   change, not something the present lock already protects [S7].
4. **Implementation admission:** after approved inputs/isolation and before GREEN,
   choose deterministic RED reuse or scoped prototype proof. No new top-level stage.
   For deterministic work reuse Step 5/6 RED and red-lock. For prompt work allow only
   the declared prototype files and runner operations before proof passes; no UI,
   deployment, broad application scaffold or surrounding integration implementation.
5. **Full implementation and final gates:** after admission, keep the existing
   GREEN firewall, review, drift and QA. The existing QA allows no-Playwright SKIPPED;
   that must not satisfy a required agent held-out evaluation [S2, S8]. Attach that
   evaluation as an additional required result within final verification.

Do not dispatch the existing GREEN architect unchanged as an early proof designer.
Its prompt prohibits test material and its current contract returns only
`files_changed`; introducing planning/proof semantics requires explicit contract
work [S3, S4]. Recommendation for implementation: a narrow, conditional design
operation with its own typed result, sharing architectural guidance and routing
policy. Keep provider choice in routing, never in the new role text [S9]. The exact
typed role/operation decision remains an implementation question below.

## Prototype and final-evaluation rules

The proposed prototype is real execution of only the minimum prompt/interaction
needed to challenge the assumption, using synthetic inputs and no student accounts
or production data. Record source/spec/scenario hashes; exact prompt/template hash;
runner binary/version; observed provider/model; configured generation options; input
fixture hash; oracle version; start/end timestamps and redacted evidence digests.
If a hosted model exposes only an alias rather than an immutable model revision,
record that limitation explicitly; never invent a pinned backend version.

The runtime is the one required by the task's contract, not whichever local model
is convenient. Capability/auth failure yields `unknown`, consumes infrastructure
budget only and blocks applicable proof. Use existing adapter/subscription admission
and actual provenance; do not add API billing fallback [S9]. Exact provider CLI names
belong in adapters only. Preserve policy/isolation requirements; absence of a supported
prototype runner is not permission to execute arbitrary model-supplied commands.

The independent evaluator fixes the development cases and oracle before execution.
Repairs may change the bounded prototype, not weaken expected/forbidden behavior to
bless a failure. A genuine requirement correction requires upstream/spec revision,
independent re-challenge and new sealed input hashes, with prior attempts retained.
The GREEN worker gets public contract semantics, not hidden test code/output [S2].

Held-out cases use separate synthetic fixtures prepared before final evaluation.
They remain unavailable to author, prototype repairer and GREEN worker. Once a
held-out case has been used to guide a repair, record it as exposed development
evidence; a new independently prepared holdout is required before claiming fresh
final validation. A final `unknown` never becomes pass because development cases pass.

## Receipts, budgets and resume

Propose a machine-readable proof receipt with `pass|fail|unknown` outcome, scenario
IDs, applicability rationale, evidence references/hashes, provenance, observed
runtime, attempt identity, counters and concrete next action. `not_applicable` is
an applicability decision, not a fourth execution outcome; it cannot hide a failed
required scenario. All required applicable scenarios must have accepted evidence.
For deterministic RED, record `expected_red_observed` as admission evidence while
keeping the test's actual failure; never report an unimplemented feature as passing.

Reuse the atomic/idempotent pending-attempt design introduced in #20 rather than
build another retry engine. Current code is scoped to extractor/adversarial dispatch
and fixed limits; extending it to proof is explicit implementation work [S10].
Proposed initial policy: one proof evaluation plus two substantive repairs,
two infrastructure failures, and an independent six-call ceiling per ticket proof
gate. Reserve before launch, finalize only after authoritative oracle mapping,
retain state across resumes, block unresolved pending attempts, and never reset
counters by changing output paths. Count runtime/capacity/auth/schema failure as
infrastructure; completed wrong behavior is substantive. Design-review calls and
prototype calls share the total ceiling; an insufficient budget blocks, not skips.

These defaults are a recommended starting point, not measured optima. Configuration
may raise bounded caps or require proof for additional classes, but may not lower
mandatory applicability, authorize shell from model output, suppress final review,
convert unknown to pass, or enable paid API fallback. Store effective policy and
its hash in receipts. No new setup question when defaults are sufficient.

Current generic controller supports implement/review/drift/qa only and counts gate
attempts differently; do not silently reuse it as a proof controller [S11]. Current
manifest validator has only four repair budget keys; new proof configuration needs
validation/installer/setup tests rather than undocumented environment overrides [S12].
Interruption/timeout/output-quota behavior must be verified in the runner before
claiming unattended containment. A retained pending receipt alone does not prove
that an orphan provider process stopped.

## Optional #8 measurements

Link proof receipt to the run/attempt identity exposed by #8 when available; do not
invent a metric API before its PR establishes it. Record elapsed time and token
usage only when observed, with null for unavailable values. Record early defects
as distinct, evidenced scenario findings, not each retry as another defect. No
prompts, fixture bodies, credentials or source content in aggregate metrics [U2].
Compare total run latency/tokens, proof cost, later repairs and escaped failures
against the #8 baseline before increasing applicability. MEX remains an optional
later context input, never an oracle or a required dependency for #13.

## Integration dependencies and acceptance tests

**#18 first for implementation:** consume its shared convention/capability resolution
and neutral project-context contract. Do not copy legacy context variables/tool
names into this feature. Actual dispatch provenance comes from current structured
`artifacts.provider/model`, not a guessed runtime identity; adversarial prose still
mentions a different envelope, a discrepancy to resolve through typed contracts
[S6, S9, U3]. **#19 paired with implementation:** add new role/command/config examples
to the scoped neutral-core regression scan; legitimate adapter/routing/auth references
remain allowed. Do not scan unrelated plugins or rewrite history [U4].

Required implementation tests (proposal):

- Deterministic small change causes no extra LLM call and reuses one RED execution.
- Missing/duplicate AC IDs, missing oracle/evidence and unknown applicability block.
- Unavailable required runtime causes zero broad implementation calls; no API fallback.
- Wrong/forbidden prototype behavior consumes substantive, not infrastructure budget.
- Transport rejection consumes infrastructure only; concurrent duplicate finalization
  and resume cannot add calls or erase counters; changed output path cannot bypass cap.
- Scenario/prompt/runtime/oracle hash change invalidates prior proof, not silently reuses it.
- Held-out content and RED source/output never enter GREEN delegation context.
- Missing Playwright does not waive required final agent evaluation.
- Independent reviewer absent or same author provenance blocks risky admission.
- Missing optional #8 metrics records null/retained receipt, not failed proof or fake zero.
- Configuration cannot disable mandatory checks; legacy project convention fallback
  and conflict fixtures exercise #18, and new core text exercises #19.

## Open implementation questions — not product questions for the user

1. Choose the typed design/proof operation boundary before adding fields: extend a
   dispatcher purpose contract, or add one conditional design-review role. Recommendation:
   dedicated typed contract sharing architectural guidance; do not overload extractor
   claim statuses or the current GREEN architect `files_changed` result [S4–S6].
2. Which existing policy-approved runner can execute the task's intended prompt runtime
   with bounded scope and verifiable child cleanup? If none satisfies it, add that narrow
   adapter/runner as implementation scope and report unsupported capability meanwhile.
   This draft does not claim a generic prompt evaluation adapter already exists [S9–S11].
3. Select a registered deterministic assertion/rubric interface and define exactly how
   independent judgment reaches `pass|fail|unknown`; provider exit zero is insufficient.
   Validate complete scenario coverage and preserve evidence, not self-reported confidence.
4. Reconcile the proof policy schema with #18's effective configuration contract and
   #8's final metrics schema after those PRs land. No new names here are installed flags.

These are bounded engineering decisions for implementation/adversarial review, not
permission to begin a live prototype or claim this design is approved. Issue #13
remains open until implementation and independent behavioral verification complete.

## Works Cited — verified source inventory

Every S-entry was inspected at the baseline commit above. Paths exist at that
commit; descriptions distinguish existing behavior from the proposed additions.

| ID | Source at inspected commit | Verified fact |
|---|---|---|
| S1 | `agents/nightshift-spec-writer.md:60-92,121-131` | Existing AC template is Given/When/Then; Test Plan and exact Sources required. |
| S2 | `commands/nightshift-implement.md:176-258` | Relevant RED assertions, test firewall, red-lock and GREEN dispatch already exist. |
| S3 | `agents/nightshift-architect.md:17-26,67-102` | Current architect is GREEN/escalation role, receives no tests, and plans before implementation. |
| S4 | `contracts/nightshift-architect.schema.json:49-73` | Current strict result is `files_changed`, not a behavioral design verdict. |
| S5 | `scripts/nightshift-contract.jq:5-27` | Validator has explicit role branches and exact keys; new role/purpose needs explicit schema work. |
| S6 | `commands/nightshift-adversarial.md:76-119,313-320` | Provenance/retry rules and NEW mapping exist; prose envelope differs from current strict dispatcher contract. |
| S7 | `scripts/nightshift-tdd-spec-lock.sh:16-37` | Current spec seal stages SPEC.md and records a lock commit; scenario sealing is proposed. |
| S8 | `commands/nightshift-qa.md:9-19,75-85` | Existing final Playwright QA permits no-suite skip; cannot substitute for required agent evaluation. |
| S9 | `scripts/nightshift-agent.sh:113-156` | Strict role assets, configured route selection, cross-provider routing and subscription admission exist. |
| S10 | `scripts/nightshift-retry-budget.py:15-54,97-131` | Pending reservations, atomic accounting, separate counters and deferred authoritative mapping exist for adversarial dispatch. |
| S11 | `scripts/nightshift-controller.sh:28-42,72-101` | Generic controller gate allowlist, container/policy requirement and gate-attempt budget semantics. |
| S12 | `scripts/nightshift-manifest-validate.sh:12-32` | Current scalar manifest parsing and four validated repair budgets; no proof settings defined here. |
| U1 | [Issue #13](https://github.com/doctor-ew/nightshift-community/issues/13) | Upstream scope, early challenge/prototype requirement, budget and delivery boundaries. |
| U2 | [Issue #8](https://github.com/doctor-ew/nightshift-community/issues/8) | Proposed baseline metrics must use observed values, preserve source and omit secrets/content. |
| U3 | [Issue #18](https://github.com/doctor-ew/nightshift-community/issues/18) | Neutral conventions/capabilities/context precede proof implementation; no active-runtime mutation. |
| U4 | [Issue #19](https://github.com/doctor-ew/nightshift-community/issues/19) | Scoped source/installed-adapter regression guard and precise compatibility allowlist. |
