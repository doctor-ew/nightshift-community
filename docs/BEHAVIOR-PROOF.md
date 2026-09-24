# Behavioral proof

Behavioral proof checks risky assumptions before full implementation. Every new
stage run requires `docs/<task-key>/behavior-scenarios.json`, including small and
documentation-only tasks. Ordinary deterministic work reuses its existing RED
execution. Only required prototype cases invoke a model.

The source document is `docs/BEHAVIOR-PROOF.md`. Installation publishes it at
`${NIGHTSHIFT_HOME:-$HOME/.nightshift}/docs/nightshift-behavior-proof.md`.
The helper is `scripts/nightshift-behavior-proof.py` in source and the installed
runtime's scripts directory. Legacy adapters receive the adjacent proof and retry
helpers through the shared installation inventory.

## Classify cases before approval

Use version 1 of the public scenario artifact. Its exact top-level keys are
`version`, `task`, `ac_ids`, `author`, `applicability`, `runtime`,
`prototype_files`, `cases`, and `heldout`. Give ACs stable IDs and map them in the
specification's Test Plan. Cases use an `ac_ids` list for many-to-many coverage.

Each case contains `id`, `ac_ids`, `required`, `applicability`, `given`, `when`,
`then`, `forbidden`, `input`, `expected`, `prohibited`, `counterexamples`, and
`visibility`. The `forbidden` field is a string describing disallowed behavior.
Required cases cover all applicable ACs. Optional cases cannot
replace required coverage. Applicability contains `kind`, `rationale`, `risks`,
and `review`:

| Kind | Required evidence |
| --- | --- |
| `deterministic` | Relevant observed RED before GREEN; actual passing ordinary tests before final approval |
| `prototype` | Independently challenged design, real development completion judged locally, then fresh held-out final completion |
| `not_applicable` | Explicit independently reviewed rationale, empty risk list and final source-scope checks |

Risks are `deterministic_logic`, `prompt_behavior`, `agent_behavior`,
`runtime_interaction`, and `safety_sensitive`. Prompt, agent and runtime risks
require prototype coverage. Safety-sensitive deterministic behavior still uses
ordinary assertions but requires independent design challenge. The top-level
kind summarizes required cases; its risks are the union of all public cases,
including optional cases. A mixed task retains
its deterministic obligations even when its summary is prototype.

Review fields start as null. A recorded classification attestation contains
`reviewer_provider`, `reviewer_author_id`, `decision`, `reviewed_input_sha256`,
and `evidence_sha256`. It records actual independent review, not a generated
approval placeholder. Existing independent classification review is sufficient
for ordinary deterministic or documentation-only cases; no extra model call is
needed merely to fill these fields. Author identities contain `provider` and
`author_id`. Typed prototype challenge also requires a different provider under the default
policy. Explicit `providers.policy = "claude-only"` permits a fresh Claude reviewer
session; the dispatcher and authoritative challenge receipt record this policy and
session-independence basis. A policy change invalidates reuse of that challenge.
Same-author classification and evidence remain prohibited.

The review digest uses canonical UTF-8 JSON with sorted keys, compact separators,
non-ASCII text preserved and nonfinite numbers rejected. Replace only top-level
`applicability.review` and each case's `applicability.review` with null before
hashing. Do not remove unrelated data fields named review. Changes to reviewed
semantics require new review evidence and invalidate prior approval.

## Supported runtime and local assertions

The original profile is `claude-subscription-text-v1`: one synthetic text input,
one sealed task system prompt and one completion, with tools, customizations and
session persistence disabled. `runtime` contains `profile`, `model`,
`cli_version`, and `system_prompt_file`; it is null when no prototype applies.
The recorded CLI version must match actual admission. Hosted model aliases do
not establish an immutable backend version; retain that limitation explicitly.

The additional `claude-subscription-multiturn-text-v1` profile accepts a case
`input` containing an ordered array of 1–16 turn objects. Every turn has exactly
`input` (nonempty text), `expected` (nonempty assertion array), and `prohibited`
(assertion array). Use the same assertion format described below. Existing
case-level expected/prohibited assertions additionally grade the final response.
All turns must pass; a failed or unknown turn ends that case immediately.

Each launch receives the sealed system prompt and explicit JSON replay of all
prior user messages and actual assistant completions plus the next user input.
This tests conversational reasoning from supplied history; it does not test
native session persistence, tool access or external memory. Each case starts
with an empty history. Assertions are never included in the model input.
Replay input is bounded to 1 MiB; transport timeout and output limits apply to
every turn. A large conversation can therefore end as unknown at that limit.

Each turn reserves and charges one existing CLI-call budget unit. Admission
requires enough remaining units for all pending turns before any model launch;
include the independent challenge call when sizing development_calls. No budget
reset or automatic increase occurs. The canonical local state retains turn
attempts, usage, outcomes, oracle/input/history/completion hashes, and partial
progress. Retained failed turns remain authoritative after interruption, even
if the final case aggregate was not written; unchanged development retries and
failed heldout retries remain blocked. Public receipts list all turn attempt IDs
and aggregate usage; raw
private conversations are not published. Changing any turn input or assertion
changes the sealed scenario digest and requires new independent review.

A task requiring tool use, another provider, persistent memory, browser execution
or another unsupported interaction blocks applicable proof. Read-only sandbox
mode alone does not establish that tools are disabled. This runner has no API
billing fallback and never evaluates model output as shell or executable code.
Subscription admission preserves the existing authentication policy. Missing
authentication or unavailable runtime produces unknown rather than pass.

Prototype cases require a nonempty input and positive oracle assertions.
`expected` assertions must all hold and `prohibited` assertions must all be
false. Empty prohibited assertions require an explicit forbidden-behavior
rationale. Deterministic and not-applicable cases can have null input and empty
oracle lists; their evidence comes from tests or reviewed applicability.

The helper's `capabilities --project <project>` operation prints supported
operators and limitations without a provider call or proof-state mutation. Use it
before writing scenarios and record unresolved evaluator requirements separately.

`text_section_contains` has exactly `op`, `start`, `end`, and `value` fields.
The start/end markers must be distinct, nonempty standalone lines; both must occur
exactly once in the completion and start must precede end. Only the text strictly
between those lines is searched for value. Missing, repeated, or reversed markers
fail the positive assertion. For required structure, use a positive section check;
a prohibited assertion alone does not prove the section exists. This is literal
containment, not semantic evidence entailment, correct ordering of facts, or a
natural-language question counter. Negative public examples should place the right
fact outside the section and omit it inside; those examples must fail.

The built-in version-1 oracle supports `text_section_contains`, `text_equals`, `text_contains`,
`json_equals`, `json_field_equals`, `json_field_length_at_most`, and
`json_field_nonempty`. Assertions contain `op` and `value`;
All `json_field_` assertions use `field`, a nonempty list of literal JSON object
keys. `json_field_length_at_most` requires an integer `value` from 1 through 16
and matches only arrays whose length is at most that value.
`json_field_nonempty` requires literal `value: true` and matches only nonblank
strings or nonempty arrays. To require one to three features, combine nonempty
and length-at-most-three assertions on the same array. Neither operator validates
the semantic quality of array members or prose; independent review remains
necessary. Missing fields and other JSON types fail these assertions. There is
no expression language, arbitrary regex, imported grader or command executor.
JSON comparisons preserve types and reject duplicate keys/nonfinite values.
Malformed task JSON is wrong behavior; missing completion or transport failure
is unknown. Provider exit zero, its status label and reviewer confidence never
substitute for the actual completion matching the local assertions.

## Normal stage sequence

The orchestrator resolves the physical project and retains task identity. Use
`--project DIR --task TASK` with the helper. A non-Git project cannot establish
the canonical task ledger and blocks applicable execution.

1. Author the spec and public scenarios together. Run `validate --scenarios FILE`.
   Complete classification review and conditional `challenge --scenarios FILE
   --out FILE` before approval. The challenge report reviews all public case IDs
   and their digest; it never receives private bodies or locators.
2. Activate ordinary task scope, seal approved spec/public artifacts and write
   meaningful failing tests for required deterministic cases. Run those tests
   once and retain their actual output. Lock those tests with the existing RED
   lock. Pure prototype/not-applicable tasks need no fabricated ordinary RED.
3. Call `seal --scenarios FILE`. Add `--challenge FILE` for prototype or
   safety-sensitive cases and `--heldout FILE` when prototype cases apply.
   The private held-out file must already be independently fixed. Runtime sealing
   follows any required RED lock; it records the source baseline and bound inputs.
4. For deterministic cases, write the trusted observation to the conventional
   stage artifact `docs/<task-key>/proof-red.json`, then call `record-red
   --evidence FILE`. For prototype cases, call `run --gate development`.
   Before GREEN, require `gate --gate development` to succeed with a pass result.
5. Dispatch engineer/architect with mandatory `--task TASK`. The dispatcher
   checks development admission itself before launching the provider. Only after
   that admission may normal declared surrounding implementation proceed.
6. Run ordinary final tests for deterministic cases, record their actual success
   in `docs/<task-key>/proof-final.json`, and call `record-final --evidence FILE`.
   After review/drift changes, refresh any stale ordinary evidence. Run required
   private cases with `run --gate final` and require `gate --gate final` before
   QA approval. Browser QA skip never waives this final proof.

`gate` and `status` only read retained state; they do not create a ledger or
consume attempts. Exit 0 means an operation succeeded; admission additionally
requires the gate's pass outcome. Exit 1 blocks for failed/unknown evidence;
exit 64 identifies invalid arguments, schema or configuration. Keep sanitized
receipts separate from raw private evidence. A missing helper/artifact, task name
without proof, stale digest or unknown outcome never permits GREEN.

Older low-level state/context helpers retain their existing interfaces. Existing
specs without scenarios must be classified and migrated before new GREEN work;
there is no grandfathered dispatcher or fixture bypass. Historical completed
work is not retrospectively labeled proof-passed.

## Test evidence and source binding

`record-red` and `record-final` ingest a trusted observation; neither executes its
recorded command. Version-1 evidence has exactly `version`, `task`, `gate`,
`observer`, `scenario_ids`, `command`, `exit_code`, `assertions`, `log`, `tests`,
`red_lock_sha`, and `source_hashes`.

The independent observer identity contains provider/author_id. Scenario IDs cover
required deterministic cases. Command contains argv and source; source contains
repository-relative path, positive line number and sha256. Resolve the exact
command through applicable project instructions before recording it. RED has an
actual nonzero exit and at least one relevant failed assertion; syntax/import
failure is not RED. Final has exit zero, at least one passed assertion and zero
failed assertions. Assertions contain kind=`relevant_assertion`, passed and failed.

Log contains an explicitly supplied absolute regular-file path and sha256; reads
are bounded at 4 MiB and symlinks rejected. Tests contain confined relative paths
and digests bound to the recorded full RED-lock commit. They remain unchanged
between RED and final. Source hashes are empty for RED and cover every declared
final source/test file for final evidence, excluding task delivery evidence.
Expected RED never satisfies final success. Model SUCCESS is not an observation
of test relevance, and hashes are integrity checks rather than protection from a
malicious same-user host forging a receipt.

Development seals bind spec, scenarios, oracle/runtime policy, scope, review,
locked tests and prototype revisions. Before development pass only the declared
prototype files may change; surrounding engine or application work is premature.
The default allowance is two recorded prototype repairs. Repairs do not change
the oracle or hidden cases; an explicitly reviewed policy amendment may extend
the cumulative allowance. An unchanged failing prompt cannot be repeatedly sampled until it passes.
After development pass, allowed surrounding changes preserve development
admission but invalidate stale final evidence. Out-of-scope edits, changed tests,
spec or oracle block. Preserve pre-existing dirty files as baseline data without
adopting their unreviewed changes as accepted implementation.

## Private cases, accounting and limits

Public `heldout` contains manifest_sha256, case_ids, author and prepared_at.
Private cases use the same manifest schema, prototype applicability, held_out
visibility and `heldout: null`; they cannot recursively hash themselves. Their
required AC union covers every required public prototype AC. Validate commitment
and union at seal; keep private bodies outside checkout, worktrees and history.
Do not include private locators in a review/implementation prompt. The no-tool
profile and input separation do not claim malicious-host filesystem security.

`expose --case ID` records known disclosure without printing hidden content.
Exposure invalidates final freshness. Replacement requires new independent cases,
commitment and review/seal while retaining budgets. Final failure does not permit
automatic repair using hidden output or treating exposed cases as fresh holdout.

The Git common directory owns one retained task ledger. Output paths, worktree
aliases and new hashes do not reset it. Reserve each reviewer/provider case call
before launch and finalize idempotently. Pending reservations block duplicate
launch; the gap between reservation and launch remains conservative unknown.
Infrastructure observations, including failed prelaunch probes, share the task
infrastructure cap. Confirmed model launches are counted separately from probes.

Defaults are eight development calls, two final calls, two prompt repairs, two
infrastructure failures, 120 seconds and 1 MiB combined provider output per call.
Count one call per case, not per suite. Independent review/re-review consumes the
development cap. A suite exceeding remaining capacity blocks before starting.
There is no separate model-repair dispatcher feature. Timeout, output overflow
or unconfirmed process cleanup yields unknown and retains accounting. No new
output path, replacement holdout or configuration file resets exhausted budgets.

Optional metrics retain observed duration/token use or null, with distinct failed
scenario IDs in proof receipts. Metrics failure never changes proof outcome. Raw
prompts, completions, fixtures, credentials, command text and private locators do
not enter aggregate metrics. This is not a claim of measured savings.

## Public development transcripts

Prototype development runs retain each available parsed completion and its public
student input in `docs/<task>/development-<attempt_id>.json`. Observation records
reference the relative path and the SHA-256 of canonical JSON. Files include the
attempt, scenario, turn index, prompt and seal hashes, outcome, and assertion
satisfaction arrays. Both `expected` and `prohibited` arrays use `true` to mean
that the corresponding requirement is satisfied; invalid JSON fails JSON
requirements. Case assertions appear only on the last turn. These diagnostics
reuse the existing evaluator and do not change acceptance semantics.

Evidence is limited to 4 MiB per charged turn, in addition to existing input,
output and call limits. The file contains only the current turn, avoiding repeated
history growth. Final runs never write these public files. Legacy literal-only runs do not retain final completion bodies; the optional source-bound profile below retains them privately.
Transport failures without a parsed completion do not retain raw provider output.
Evidence write failures leave `development_evidence_error: artifact_unavailable`
in the aggregate observation without changing grading or retry accounting.
Historical runs with completion hashes only cannot be reconstructed by this change.

An engine update invalidates existing seals. A runtime-only reseal with unchanged
scenario, specification and policy requires a new independent challenge and the
same prototype. It retains previous failure seal identities and all counters, so
an unchanged failed prompt remains blocked. Subsequent prototype changes consume
the ordinary repair budget. Resealing is not permission to resample failed work.

## Explicit completion format contract

The optional runtime field `response_normalization` accepts `none` (the default)
or `json-or-single-fence-v1`. The latter permits JSON assertions to parse either
raw JSON or exactly one whole fenced block, with an optional lowercase `json`
label and line breaks after the opening fence and before the closing fence.
Surrounding whitespace is allowed. Extra prose, multiple blocks, another language
label, malformed JSON, duplicate keys and nonfinite values fail JSON assertions.
This setting is bound into reviewed public and private runtime metadata and the
seal. It is not an automatic fallback after failure.

Only the JSON assertion parser unwraps the response. Text assertions, prohibited
text checks, actual conversation replay and retained public completions use the
original response. Metadata, scenario files, accounting state and provider result
envelopes continue to require strict JSON. Oracle operators and their semantic
meaning are unchanged.

Changing the format contract requires explicit product authorization, independent
public classification and challenge, an independently updated matching private
runtime/commitment, and a new public specification lock and seal. Historical
failures remain in the ledger; they are not relabeled as passes. New development
and final observations must pass under the new seal. Reseal the unchanged
prototype before applying another prompt repair, so the repair remains counted.

## Explicit cumulative policy amendments

The separate adversarial-dispatch retry ledger supports an operator-invoked
`nightshift-retry-budget.py authorize-continuation` action with `--state`,
`--decision`, `--expected-sha256` (the exact current ledger bytes), and
`--attempts` (one to three). Use it only following explicit user authorization
to continue a stopped review. The dispatcher never invokes this action itself.
It records the decision path/hash, prior ledger hash and counters, and new
absolute review ceilings in `continuations`; original counters, attempts and
base limits remain intact. Replaying the same decision cannot replenish calls.
Every additional dispatch consumes the allowance, including successful calls.
Pending calls and exhausted infrastructure limits are ineligible. This action
does not approve a gate or amend the separate behavior-proof policy below.
The decision file is an audit record, not an authentication boundary against
processes already able to write the ledger. Preserve it with the run evidence.

A pinned policy cannot be changed by editing configuration and rerunning. The
`amend-policy --evidence <path>` operation records an explicitly authorized,
independently reviewed increase before a new challenge and seal. It permits only
increases to cumulative `development_calls` and `final_calls` up to 128, and
`repairs` up to 64. These are finite ceilings, not default allowances. Existing
pinned limits remain authoritative until the reviewed amendment is applied. Defaults remain two repairs, eight development calls and two final
calls. All other policy fields remain unchanged. Pending attempts block amendment.

The evidence JSON has exactly these fields:

- `version`: integer 1; `task`: the existing task identifier.
- `previous_policy_sha256`: canonical JSON digest of the pinned policy.
- `policy`: the complete proposed policy, equal to the current configuration.
- `rationale`: a nonempty explanation of the authorized continuation.
- `authorization`: `path` under the task documentation directory and `sha256`
  of the nonempty file recording the user's explicit authorization.
- `review`: `provider`, `author_id`, `decision: approve` and
  `reviewed_input_sha256`, computed over the evidence with `review: null`.
  The reviewer must differ from the public scenario author.

The operation verifies authorization bytes, the review digest, the prior policy,
and the exact target. It appends the complete amendment evidence, previous policy,
current counters and timestamp to `policy_amendments` and updates only the pinned
policy limits. It preserves all attempts, used counters, observations, exposures
and prior seals. Replaying stale evidence fails. A retained authorization record
is trusted human-review evidence, not cryptographic proof of a user's identity.

For example, increasing a repair cap from two to five with two already used leaves
three repairs available. The change does not reset the used count. Run a fresh
independent challenge and reseal the unchanged prototype before the next repair.
A policy-only reseal retains failed-prompt restrictions; it cannot authorize
resampling unchanged failed work. A separately authorized format-contract change
requires the reviewed scenario amendment described above. Preserve every earlier
failure and budget receipt when publishing the continuation.

## New prompt artifact ordering

For a greenfield prompt task, `commands/nightshift-spec.md` Step 3.5 permits
preparing only the declared minimal prompt candidate before design validation.
It remains unapproved and must not be executed in that phase. This resolves the
existence/hash prerequisite without weakening design challenge, private held-out
commitments, budget pinning, or development/final proof. Application code and
harness implementation still follow approved scope and the ordinary build gates.

## Optional source-bound completion evaluation

A prototype case may add `evaluation`; multiturn cases may also add it to each
turn. A case contract evaluates the last completion with its actual conversation
history. Turn contracts evaluate that turn. Legacy cases retain their literal
oracle behavior. This is text-only supplied-source evaluation, not evidence that
an application retrieved a document or exercised real tools.

```json
{
  "version": 1,
  "sources": {"S1": "Allowed choice is allow."},
  "structure": {
    "headings": [],
    "terminal": "",
    "citation_section": "",
    "citation_end": ""
  },
  "criteria": [
    {"id": "grounding", "requirement": "Every claim must be supported by S1; do not overstate the source."}
  ],
  "evaluator": {
    "provider": "local",
    "model": "configured-installed-model",
    "independence": "different-provider"
  }
}
```

The contract has exact keys. All source values must occur literally in the actual
input. When actual user input has explicit `[ID]` source blocks, the ID must exist and
the value must occur in that ID's block; an arbitrary other source cannot supply its excerpt. Assigned
locators and whole-user-input request aliases are allowed only without supplied
source IDs. Mixed labelled-source and whole-request aliases are unsupported. Multiturn source checks inspect decoded user messages,
excluding assistant completions; the serialized generation input remains bound.
The sealed mapping and rubric require independent design review. This mechanical
binding does not itself establish semantic truth.

`headings` specifies every exact level-two Markdown heading in order; an empty
array disables that check. `terminal` requires the unique last line, with no
trailing content. Citation sections are delimited by exact unique heading lines.
Each nonblank entry must be `[ID] locator, "exact excerpt"`; excerpts must occur
in that ID's source. Used IDs and listed IDs must match exactly; unknown, duplicate,
missing, unused and wrongly bound entries fail. Empty citation delimiters disable
citation checks. This deliberately bounded grammar does not parse arbitrary
Markdown citation formats.

`structure.blocks` is optional and has exact keys `start`, `end`, `heading_prefix`,
`fields`, `labels`, `count_prefix`, `count_suffix`. Between the two exact boundary
lines, each block starts with `heading_prefix`; its nonblank field lines must
match `fields` in order. `labels` maps selected field prefixes to allowed exact
values. The unique count line must equal `count_prefix + block_count + count_suffix`.
Use a semantic criterion for required prose when a case legitimately has no blocks.

The semantic evaluator receives the source map, actual input, system prompt,
conversation history, actual completion and sealed criteria. Its strict transport verdict must echo the payload hash, cover every criterion
exactly once, and provide exactly `id`, `status` (`pass`, `fail`, `unknown`),
`line_id` and `reason`. The requested `line_id` field accepts only a completion
line key such as `L23` (empty only for fail/unknown omissions), never literal text.
The controller resolves this to the canonical `quote` field for verification.
Legacy transport items with `quote` instead of `line_id` remain compatible: they
accept a line ID or an exact unique completion-line value. Mixing both fields in
one item is rejected. Numbered
completion lines are bound into the payload. Literal compatibility accepts only
an entire nonblank original completion line of at most 160 characters whose
`completion_lines` value occurs once in the mapping. A truncated preview of a
longer original line is not accepted as literal evidence; use its line ID. Paraphrases, partial matches, ambiguous repeated values
and multiline text are rejected; use the line ID to disambiguate repeated lines.
Existing ID strings are reserved solely as IDs in both forms: if line `L2`
contains the text `L1`, use `L2` to cite that text; `L1` always selects line one. The
controller resolves each selected line to its actual first 160 characters before
strict quotation validation; unknown references are rejected. Original transport
and resolved quotation verdicts are retained privately. Recheck reparses the raw
provider response using sealed normalization and compares both derived verdicts.
Only all-pass admits the case. Missing fields, duplicate keys, unsupported quotes,
unknown status, requested tools, invalid JSON, stale evidence and transport errors
block admission. A matching quotation is an integrity check, not a substitute for
the judge assessing the entire response. Evaluate model reliability with public
positive and negative calibration before relying on a configuration.

The standard policy requires an evaluator provider different from both the
scenario author and the Claude generation provider. The supported transports are
loopback local OpenAI-compatible HTTP (without tools or redirects) and a fresh,
safe-mode Claude subscription session with tools/MCP/session persistence disabled.
Claude requires explicit `claude-only` policy and `independence: "fresh-session"`.
Codex is supported only through the pinned, capability-verified subscription
adapter described below. No provider fallback occurs.

Routing follows `NIGHTSHIFT_ROUTING_FILE`, then the project's `routing.file` or
`providers.routing_file`, then the checkout routing file. Local connection settings
are under `local`: `backend`, `base_url`, optional `auth_settings_file`. Supported
backends are `omlx`, `ollama`, `lmstudio`, and `openai-compatible`; endpoints must
be HTTP loopback. Authentication settings must be private and owned. Credentials
are not logged. Configured `local.reasoning_effort` (nonblank string or finite
number) is forwarded unchanged. Optional `evaluation_chat_template_kwargs` accepts
only `{ "enable_thinking": true|false }` and is forwarded as `chat_template_kwargs`;
no thinking setting is imposed by default. `evaluation_response_format` selects `json_object` (default),
`json_schema`, or `none`; every selection still uses the same strict local verdict
validator. `evaluation_response_normalization` is `none` by default; explicit
`json-or-single-fence-v1` permits one whole-output JSON fence, while chatter and
multiple fences still fail. Verdict quotes are exact nonblank single-line substrings
of at most 160 characters (empty only for fail/unknown omissions); reasons are
nonblank and at most 240 characters. Provider and model are explicit configuration, never automatic fallback.

Generation is finalized and persisted before reserving evaluation. Every judge
launch consumes one existing gate call with kind `evaluation`; limits and retained
failures are never reset. Minimum admission includes generation and judge calls.
Pending attempts block further admission after interruption. Usage totals include
both transports, while run metrics identify their separate providers. Unknown
usage remains unknown. Failed structure does not launch or charge a model judge. Pre-reservation unknown
source/schema/storage failures consume infrastructure allowance as unlaunched
probe failures; generation counts remain unchanged.

For this optional contract, final completion bodies and raw judge output are retained
in mode-0600 evidence files under a mode-0700 directory beside the controller's
external heldout manifest. Development evaluator evidence and source-evaluated generation transcripts are
retained under the private proof state directory. Unsafe/symlink paths fail closed. Public receipts
contain hashes, status, counters and usage, never final inputs, response bodies,
judge quotations or private evidence paths. Final gate rechecks private evidence,
contract/completion/payload hashes, the evaluator engine and routing configuration.
It reconstructs the conversation from sealed user inputs and retained raw generation
responses, verifies their output/completion hashes, and cross-checks evaluator input,
history, completion and system prompt against that generation record. Missing or
altered generation evidence blocks admission.
Changes require fresh evaluation and ordinary resealing rules; old receipts are
never promoted into semantic proof. Public and private manifests must both enable
case evaluation for acceptance criteria requiring it. Private-only evaluation is
rejected at sealing before any evaluator reservation.

Run `bash tests/test-source-evaluation.sh` for offline contract, HTTP-transport,
accounting, private retention and tamper coverage. These fixtures prove harness
boundaries, not a live model's semantic accuracy or application retrieval behavior.


### Pinned Codex subscription evaluator

`evaluator.provider: "codex"` selects the native Codex CLI adapter. Model selection
remains explicit in the contract; no model is hard-coded. Standard independence
still rejects an evaluator that shares the scenario author's provider, and
`claude-only` policy still rejects Codex. `allowed_providers` in routing is also
enforced at sealing and before the evaluator launch.

The supported adapter is pinned to **codex-cli 0.155.1**. Before copying any
credentials, it runs an unauthenticated loopback request probe with the selected
model and verifies that the outbound tools list is empty. Unknown versions,
nonempty tools, unsupported capability output, or a missing probe request stop
before a model call. CLI version equality alone is not treated as proof of an
empty tool surface.

A derived model catalog disables shell, patch, experimental tools, collaboration,
Responses Lite and websockets; it replaces model instructions with the evaluator
system instructions. Active feature flags are disabled except host-skill-discovery
suppression. Deprecated flags must already be false; removed flags are not used.
The adapter ignores user configuration and rules, disables web search and interactive
tools, and uses a fresh ephemeral read-only session in an isolated private home.

Optional routing configuration:

```json
{
  "allowed_providers": ["claude", "codex"],
  "codex_evaluation": {
    "model_catalog_file": "/absolute/path/to/models_cache.json",
    "auth_file": "/absolute/path/to/auth.json",
    "reasoning_effort": "low"
  }
}
```

Omitted paths default to the original Codex home's `models_cache.json` and
`auth.json`. The selected model must exist uniquely in the catalog. An optional
reasoning effort must be listed in that model's metadata. Authentication must be
an owned private ChatGPT subscription file, with no API key. Only subscription
authentication is copied to the temporary home; native `codex login status` must
confirm ChatGPT. API credentials, provider URLs, remote-session variables and
proxies are not inherited. Production calls force the built-in OpenAI provider
and ChatGPT login, with no API or local-provider fallback.

The output schema requests `line_id` evidence. Strict JSONL parsing requires one
completed turn and exactly one final agent message, preserves input/output token
usage, and rejects any tool event or malformed/error event. Raw JSONL (including
reported cached-token usage) and capability hashes are retained privately; replay
reparses the same bytes before accepting the canonical verdict. The Codex helper
is included in both proof-engine and evaluator-payload fingerprints.

Capability probing, authentication and generation share one elapsed deadline.
Only the production subscription CLI invocation triggers the evaluator launch
counter; the loopback probe contacts no model. A production CLI startup failure
still consumes that invocation. Native transport retries can occur inside one CLI
invocation; the controller does not claim its launch counter counts backend HTTP
attempts. Safe failure diagnostics retain category, phase, exit code and stderr
hash, without credential-bearing stderr text. The adapter currently bounds its serialized
payload to 96,000 UTF-8 bytes because it passes the prompt directly to the native
CLI. Unsupported or oversized inputs fail closed. This profile establishes bounded
text evaluation, not application tool execution or retrieval evidence. A fresh live
subscription calibration is still required for any selected model and rubric.
