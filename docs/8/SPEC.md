# 8 — Deterministic preflight and per-run measurements

Status: repaired draft, NOT approved. Repair author: Codex. This revision does not
inherit the prior Claude spec-writer's authorship or approval. Independent review
must use Codex as the author provider. Baseline: branch `nightshift/8`, commit
`bea0b3935f03a10e3c50b9db391039e1d85d76ad`. Sources regrounded after the audited base refresh.

## Problem

The factory checks the project, initial commit and manifest before launching a
worker, including automatic setup on a failed manifest check [S1]. Ticket resolution
and worktree preparation occur inside the engineering command [S2]. Thus local
input and retained-worktree failures can consume a model invocation first. The
upstream ticket requires deterministic admission and observed per-run measurements,
not reduced verification or a new deployment gate [T1].

Existing role telemetry records role/provider/model/timestamps/status [S3]. A retry
helper increments persisted counters [S4]. Neither fact justifies excluding stage
or repair observations from this ticket. Unknown usage must remain null [S5].

## Technical Constraints

- Reuse the manifest, ticket-source, batch resolver and worktree policies; do not
  duplicate validation predicates [S1, S6, S7, S8, S9].
- Admission is read-only toward source and ownership: no reset, stash, commit,
  artifact move, ownership update, lock-directory creation or setup migration.
  Writing a separate observational receipt is not ownership reconciliation [T1].
- Preserve baseline failure text and exit 66 from factory lines 133–134 [S1].
  Baseline checks currently apply only when branch is not `none`; the new collision
  check likewise applies only to isolated runs as a proposed policy, not an existing
  factory behavior [S1, S2].
- Preserve subscription default, credential stripping, explicit-only API selection
  and all downstream gates [S10, T1]. A process exit zero is not verified delivery.
- Do not invoke the cached capability helper in read-only admission: its stale-cache
  path creates directories and probes tools [S11]. No optional tool absence may
  silently turn an unperformed collision check into a pass.
- Ticket output: isolated branch and PR to `integration/nightshift`; no main merge,
  deployment or installed-runtime change in this ticket [T1].

## Solution Design

All interfaces below are proposed, not claims that these commands already exist.

### 1. Deterministic admission

Add `nightshift-preflight-check.sh` with required `--project DIR`, `--branch VALUE`
and exactly one of repeatable `--ref REF`, `--batch-input TEXT`, or `--resume FILE`.
Optional `--base REF`, `--root DIR` and `--requires REF` are passed unchanged to the
worktree checker. Reject duplicate singleton flags, missing values and combinations
with machine-readable usage failure. Paths are resolved relative to project.

Factory invokes this helper after argument validation and before setup, dashboard,
authentication probes or worker launch. Its existing explicit setup subcommand is
not removed. Automatic setup/migration must not occur inside a failed admission;
the failure receipt tells the user to run setup explicitly, then retry.

Checks execute in deterministic order: project/baseline, input resolution, manifest,
then collision checks. Extract the baseline predicate to one reusable helper while
retaining the exact existing message/66. Use the existing manifest validator and
manifest-path resolver without copying their TOML rules [S1, S6].

Extend ticket-source with a read-only identity mode, `--derive-id REF --project DIR`.
Factor source classification/ID conversion for reuse by normal resolution. Explicit
upstream IDs are derived without fetching their bodies. GitHub owner/repo-qualified
references retain the existing issue-number task ID [S8]. Spec references reuse the
existing validator and identity computation, discarding body/title from the admission
result [S7]. Existing task folders use their key; bare bead resume uses the existing
local mapping rules [S2]. Missing or ambiguous local mapping returns
`TASK_UNRESOLVED`, not a skipped check. GitHub and spec IDs do not depend on Beads.

Explicit batches reuse `nightshift-batch-resolve.sh`; resume loads and validates
the supplied JSON read-only and checks tickets whose recorded status is not complete
or skipped. No batch initialization/update helper runs during admission. Check all
selected ticket IDs before starting the outer provider. A source query that cannot
be expanded by the deterministic local resolver returns `INPUT_RESOLUTION_REQUIRED`
with guidance to supply explicit refs or a resume file. This deliberately prevents
a model being used merely to discover the IDs needed for admission; general remote
query expansion is not implemented by this ticket [S9]. Record this limitation in
user documentation rather than silently bypassing collision checks.

Extend worktree with `check TASK --project DIR [--base REF] [--root DIR]
[--requires REF]`. Refactor shared receipt/schema/ancestry/registration/dirty and
unowned-target/branch predicates into functions used by check and prepare. `check`
must branch before metadata mkdir/lock acquisition and return before all creation or
receipt publication. Existing prepare continues to acquire its lock and apply the
same predicates; check is advisory and never authorizes bypassing prepare [S12].
An explicit base and prerequisites must be resolved again at the mutating boundary;
do not claim the existing pre-lock resolution already provides this [S12]. A
non-auto named branch that cannot map to the helper's managed branch must fail with
`BRANCH_POLICY_UNSUPPORTED`, not check a different branch and report success.

Admission emits exactly one JSON object with schema_version=1, status=ok|blocked,
checks (fixed check names and pass/fail/not_applicable), reason (enum), next_action
(enum), and task IDs only when resolved. No provider output or input contents appear.
Exit 0 only for ok. Preserve baseline66 and spec65; use new translated exits67 for
collision,68 for manifest and69 for unresolved local prerequisite. Usage is64.
Reason enums include BASE_MISSING, SPEC_INPUT_INVALID, MANIFEST_MISSING,
MANIFEST_INVALID, WORKTREE_COLLISION, TASK_UNRESOLVED, INPUT_RESOLUTION_REQUIRED,
BRANCH_POLICY_UNSUPPORTED and USAGE. Manifest68 is a new translation of validator
exit1, not an existing validator exit code [S6]. Human guidance is fixed text keyed
by reason; underlying path/error text is not copied into metrics.

### 2. Run-linked observation, not guessed metrics

Add `nightshift-run-metrics.py`, a single versioned writer/validator shared by factory,
dispatcher and retry helper. Factory creates a random run ID, monotonic start clock
and private run directory under the Git common metadata directory's
`nightshift/runs/<run-id>/`. Pass a validated run-context path and run ID through the
environment to child helpers, including across worktree changes. Never infer run
membership from file modification time or scrape historical unrelated trackers.
This new storage choice does not claim state-dir always returns .nightshift; it can
select legacy homes [S13]. Reject symlink components and non-owned run contexts.

Use immutable unique event files (exclusive creation/UUID), plus an atomic summary
replacement. Create temporary files in the same directory; readers enumerate only
final `.json` event names and ignore temporary entries. Synchronize summary rebuild
with a per-run lock. This guarantees complete final records, not that no temporary
file ever exists. Separate run IDs prevent two calls for the same ticket/time from
clobbering one another. Metadata failure must not change provider exit or approve a
gate; emit a fixed metrics-unavailable warning. If Git metadata is unavailable,
emit the failure receipt on stdout and report persistence unavailable explicitly.

Persist schema_version, run_id, elapsed_seconds, terminal_status, preflight_reason,
observations, repair_count and usage. Terminal enum: running, preflight_blocked,
provider_exited_0, provider_exited_nonzero, interrupted. It intentionally has no
"verified complete" inferred from a child exit. An interruption writes the terminal
record without invoking a provider again. SIGKILL may leave running, documented as
unverified liveness, not rewritten to success.

Each observation carries an invocation ID, stage, provider, model, role, duration,
status and usage values when observed. Extend dispatcher telemetry to emit these
allowlisted events alongside its existing lifecycle output [S3, S14]. Assign stage
using a reviewed static role-to-stage mapping for unambiguous stage roles; ambiguous
roles get null unless the invoking command supplies an enum stage. Preserve selected
model separately from actually reported model; the empty factory MODEL is null, not
an observed model [S1]. Store validated provider/role enum and a model identifier only
from the resolved routing/provider metadata, never from arbitrary submitted metrics
text. Unknown identifiers become null with a fixed diagnostic code. Identifier
syntax is not evidence that a value cannot be a secret.

The retry helper emits an event only after a successful persisted increment, with
counter key, old/new numeric values and unique event ID [S4]. Aggregate run-local
deltas once, never sum historical absolute counters or count transport retries as
substantive repairs. The dispatcher may expose transport attempts separately; they
do not increment repair_count. No events means unknown/null unless a validated
complete observation scope explicitly proves zero. Events already written remain
idempotent if consumed twice. Preserve existing retry increment behavior and budgets.

Extract tokens only from documented structured provider envelope fields already
available at the dispatcher boundary; add fixture-backed parsers to the metrics
helper. Claude result usage input_tokens/output_tokens and Codex structured
turn.completed usage input_tokens/output_tokens are candidate parser contracts to
validate with captured sanitized fixtures before implementation claims support.
Do not enable a new provider output mode without a compatibility test of the final
role contract. Current Claude stdout is parsed as an envelope; Codex final contract
is a separate file [S14]. If the current transport exposes no usage envelope, record
null, but test that a genuinely reported supported envelope is captured rather than
always omitted. Never regex token counts out of free text, estimate billing or read
usage from model-authored artifacts. Track reported components and coverage; run
totals remain null if any participating invocation's usage is unknown. Partial
reported sums may be a separate explicitly partial field, never an all-run total.

The metrics boundary accepts only typed allowlisted fields. Drop prompt/result/body,
source paths/content, raw reference/query text, full commands, arbitrary env values,
stderr, credential/header/cookie data and unknown nested properties. Numeric usage
must be finite nonnegative integers with explicit bounds; elapsed time finite and
nonnegative; timestamps parsed as UTC; strings have field-specific length limits.
Model/role metadata must additionally be checked against trusted routing registries
and scrub known inherited credential values; syntactic validity alone is insufficient.
Metrics are observational private metadata, not a secret-scanning guarantee for
maliciously poisoned configuration. Tests seed secrets in ordinary allowed-looking
strings as well as prohibited fields and ensure none enter persisted output.

## Files to Change

| File | Change | Why |
|---|---|---|
| `scripts/nightshift-baseline-check.sh` | ADD shared baseline predicate | Admission |
| `scripts/nightshift-ticket-source.sh` | MODIFY shared identity-only resolution | Admission |
| `scripts/nightshift-worktree.sh` | MODIFY shared read-only check | Admission |
| `scripts/nightshift-preflight-check.sh` | ADD deterministic admission coordinator | Admission |
| `scripts/nightshift-run-metrics.py` | ADD typed run/event writer and usage parsers | Measurements |
| `scripts/nightshift-factory.sh` | MODIFY admission and run lifecycle integration | Admission, measurements |
| `scripts/nightshift-agent.sh` | MODIFY run-linked role/provider/usage observations | Measurements |
| `scripts/nightshift-retry-increment.sh` | MODIFY observed repair delta emission | Measurements |
| `tests/test-factory-preflight.sh` | ADD provider-counter/read-only regression fixtures | Admission proof |
| `tests/test-run-metrics.sh` | ADD typed, privacy, concurrency and linking tests | Measurement proof |
| `tests/test-factory-auth.sh` | MODIFY fixtures for admission dependency wiring | Compatibility |
| `tests/test-agent-dispatch.sh` | MODIFY fixtures for metrics integration | Compatibility |
| `docs/RUN-MEASUREMENTS.md` | ADD usage, limitations and receipt guidance | Documentation |
| `docs/EFFICIENCY-ROADMAP.md` | ADD links to follow-on issues | Roadmap |

## Acceptance Criteria

1. Given a missing baseline for an isolated run, invalid/unreadable/empty/oversize
   spec, invalid effective manifest, dirty retained worktree, unowned branch/target,
   or invalid receipt, when factory runs, then a typed actionable admission receipt
   precedes any provider invocation and stub invocation count is zero. Valid .md and
   .markdown files work; effective manifest selection retains existing precedence
   [S6, S7]. `--branch none` skips only isolation/baseline checks, not input/manifest.
2. Given caller files, ownership receipts, retained artifacts and absent metadata
   directories, when admission runs, then source/ownership bytes and directory
   inventory are unchanged. Observational run metadata is isolated and explicitly
   accounted for. No automatic repair/move or setup occurs on failure.
3. Given explicit single/batch/resume inputs, when admission resolves tasks, then
   every selected task is checked using the same identity and policies as prepare.
   Missing Beads does not skip GitHub/spec checks. Unsupported query or named-branch
   mapping fails with concrete guidance before provider start.
4. Given concurrent runs and nested worktree role dispatch, when observations and
   repairs occur, then separate versioned run records contain measured elapsed/status,
   preflight reason, observed stage/provider/model, run-local repair deltas and only
   genuinely reported token counts. Missing observations are null. Terminal child
   success does not assert stage approval or delivery.
5. Given secrets/prompts/source text in input, env, provider envelopes and unknown
   properties, when metrics persist, then output contains only safe typed observation
   fields and none of the seeded sensitive strings. No raw transcript or billing
   estimate is retained. Duplicate events and concurrent writes do not double count
   or corrupt final records.
6. Existing subscription-only defaults, no automatic API fallback, role contract
   validation and downstream verification gates remain unchanged. Regression tests,
   user documentation, follow-on issue links, Works Cited and independent review
   are required before delivery [T1].

## Test Plan

Use existing stub-provider style [S15], add counters for all invocation paths,
including role children and authentication probes. Compare byte hashes plus directory
inventory before/after read-only checks; account separately for allowed run metadata.
Exercise absent/stale capability cache without invoking that cache writer. Test
relative/absolute spec paths, .markdown, UTF-8 error, 1MiB boundary, permissions,
branch none, all explicit IDs, malformed resume, two batches targeting the same task,
recorded-base conflict and unowned branch/path. Confirm prepare still revalidates.

For metrics, test two concurrent runs with identical task/start time, concurrent
events in one run, duplicate event IDs, out-of-order events, unrelated historical
telemetry, worktree context propagation, zero versus unknown usage, partial usage,
successful and failed repair writes, signal exit and metrics-directory errors. Feed
supported provider fixtures plus missing/malformed/negative/string/overflow counts.
Verify opaque provider output remains compatible and no secret-looking seeded value
survives allowlisting/redaction. Run all existing offline suites and diff checks;
independent review checks source claims and all six upstream criteria [T1].

## Risks and Dependencies

The check/prepare interval is a race: only prepare authorizes mutation. Persisted
metrics add I/O and must remain nonfatal and bounded. A query now needing explicit
refs is a documented admission limitation, not a hidden successful check. Model
selection metadata is distinct from provider-reported actual model. Usage parsers
must be fixture verified; unsupported transport usage remains unknown, not fabricated.
Do not introduce MEX, dashboard redesign, caching, routing optimization, behavioral
gates or transport-retry policy changes here. Link #9–#14 and #18–#20 as follow-on
references without claiming their current completion state.

## Open Questions

No unresolved product choice is required to draft this scope. Provider usage-field
support is a verification dependency: confirm sanitized structured fixtures during
implementation; unsupported formats must be explicitly documented and null. This
draft itself still requires independent adversarial verification and approval.

## Model Router

**Decision:** nightshift-architect

Fourteen files across scripts, tests and docs; shared admission and measurement
contracts require coordinated implementation. The decision selects a role, not a model.

## Sources

Works Cited — each repository entry below was read at branch `nightshift/8`, commit
`bea0b3935f03a10e3c50b9db391039e1d85d76ad`. These are manually regrounded citations,
not a claim that the prior extractor approved the repaired draft.

- [T1] https://github.com/doctor-ew/nightshift-community/issues/8 — upstream task and
  all six acceptance criteria; fetched with GitHub CLI during this repair.
- [S1] `scripts/nightshift-factory.sh:129-151` — baseline, manifest/setup and model resolution.
- [S2] `commands/nightshift-eng.md:117-170` — reference identity and inner worktree preparation.
- [S3] `scripts/nightshift-agent.sh:14-35` — observational role telemetry fields and atomic final replacement.
- [S4] `scripts/nightshift-retry-increment.sh:20-29` — reads old persisted counter and writes increment.
- [S5] `docs/NIGHTSHIFT-COST-POLICY.md:17-19` — unknown usage, no weakening verification.
- [S6] `scripts/nightshift-manifest-path.sh:6-10` and `scripts/nightshift-manifest-validate.sh:5-33` — effective manifest, validation and error exit1.
- [S7] `scripts/nightshift-spec-source.py:9-39` — Markdown validation, stable identity, output and exit65.
- [S8] `scripts/nightshift-ticket-source.sh:44-85` — source detection and GitHub source-ID derivation.
- [S9] `scripts/nightshift-batch-resolve.sh:26-79` and `commands/nightshift-batch.md:64-108` — explicit resolver and delegated query distinction.
- [S10] `scripts/nightshift-factory.sh:171-188` — subscription default and explicit API policy.
- [S11] `scripts/nightshift-capability.sh:36-60` — stale-cache directory creation and tool probes.
- [S12] `scripts/nightshift-worktree.sh:32-77`, `scripts/nightshift-worktree.sh:125-153`, `scripts/nightshift-worktree.sh:187-210` — arguments, pre-lock base resolution, receipt and collision predicates, mutations.
- [S13] `scripts/nightshift-state-dir.sh:45-68` — canonical/legacy state selection and create behavior.
- [S14] `scripts/nightshift-agent.sh:175-229` — provider output boundaries, envelope validation and provenance.
- [S15] `tests/test-factory-auth.sh:17-27` — existing stub login/provider output fixture.
