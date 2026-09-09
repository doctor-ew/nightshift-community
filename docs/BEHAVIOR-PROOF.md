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
`author_id`. Typed prototype challenge also requires a different provider.

The review digest uses canonical UTF-8 JSON with sorted keys, compact separators,
non-ASCII text preserved and nonfinite numbers rejected. Replace only top-level
`applicability.review` and each case's `applicability.review` with null before
hashing. Do not remove unrelated data fields named review. Changes to reviewed
semantics require new review evidence and invalidate prior approval.

## Supported runtime and local assertions

The supported profile is `claude-subscription-text-v1`: one synthetic text input,
one sealed task system prompt and one completion, with tools, customizations and
session persistence disabled. `runtime` contains `profile`, `model`,
`cli_version`, and `system_prompt_file`; it is null when no prototype applies.
The recorded CLI version must match actual admission. Hosted model aliases do
not establish an immutable backend version; retain that limitation explicitly.

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

The built-in version-1 oracle supports `text_equals`, `text_contains`,
`json_equals`, and `json_field_equals`. Assertions contain `op` and `value`;
field equality also uses `field`, a list of literal JSON object keys. There is
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
Up to two recorded repairs may change the prototype, not its oracle or hidden
cases. An unchanged failing prompt cannot be repeatedly sampled until it passes.
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
