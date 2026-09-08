# Provider-neutral core and project context

Status: proposed; independent cross-provider review required before implementation.
Delivery: integration/nightshift. No installation update or Coach changes.

## Solution

Add one read-only project context resolver. Proposed new interface:
`scripts/nightshift-project-context.py [--project DIR] [--scope DIR] [--root-only]`.
Explicit project wins, otherwise NIGHTSHIFT_PROJECT_DIR, legacy CLAUDE_PROJECT_DIR,
Git root, cwd. Conflicting environment roots block unless explicit project is given.
Canonicalize physical paths. Scope must remain inside the selected project.
Return applicable AGENTS.md and CLAUDE.md files along the root-to-scope ancestor
chain only. Return a validated optional [tests].command from the canonical manifest;
never execute configuration or infer a shell command from arbitrary prose.

Add a shared convention policy in docs/PROJECT-CONTEXT.md. The active runtime reads
all returned instructions, preserves exact commands/flags, uses AGENTS.md first,
legacy conventions only for missing guidance, and blocks contradictory explicit
commands (including configured commands). Discovery is not approval to execute.
Record command and source in the stage receipt. No command is executed by the resolver.

Translate legacy environment context only at the resolver/adapter boundary.
Callers use the neutral variable. Explicit controller/ticket switches clear stale
legacy context through a shared resolver shell emission mode, with quoted values. The new --shell mode emits a safely quoted export of
NIGHTSHIFT_PROJECT_DIR and an unset of the legacy variable; this output alone may
be evaluated. The --cwd-default option preserves hook cwd fallback. Root-only
and shell modes resolve identity without reading manifests or conventions.
Preserve existing cwd-default launcher and hook behavior explicitly.

Extend the existing capability helper with a read-only semantic document lookup
from an explicit adapter mapping file. Validate operation, tool name and runtime
availability; the core requests document access without hard-coded MCP identifiers.
Absent mapping is unavailable, preserving the optional empty-context fallback.
No network/cache probing in this lookup. Existing CLI capability behavior stays intact.
New lookup syntax: --resolve document-read --mapping FILE --available-tools FILE.
Mapping JSON is {"document-read":"tool_identifier"}; available tools JSON is an
array of exact runtime-discovered names. A valid unavailable lookup exits 1 with
a JSON status; malformed configuration exits 64. Tool identifiers match
[A-Za-z_][A-Za-z0-9_]*. Lookup returns data and never executes tools.

The optional tests setting must be a TOML table; command must be a non-empty
string without NUL or line breaks. Preserve every other byte, including flags.
Validate through the resolver from manifest admission after existing manifest
checks; absent manifests are allowed by discovery but still rejected by admission.
A tests scalar or non-string/blank command is invalid. Root-only mode skips this.

## Acceptance Criteria

1. Shared discovery yields physical roots, applicable ancestor convention paths,
   configured test command provenance, and typed conflict/errors without writes.
2. Explicit project overrides environment disagreement; otherwise disagreement
   blocks. Ticket/controller transitions do not reuse stale legacy roots.
3. Canonical malformed/unreadable manifests block without legacy fallback.
   Configured test commands retain exact strings; invalid types/empty strings block.
4. Runtime-neutral roles/stages use the shared convention policy, preserve legacy
   fallback and block conflicting commands rather than guessing. Optional missing
   tools retain their existing fallback. No provider-specific document tool in core.
5. Existing auth, retry budgets, preflight ordering, isolation, legacy state lookup,
   deploy JSON precedence and independent review gates remain intact.
6. Focused tests plus existing offline regressions and independent review pass.
   A deterministic discovery test is not proof of arbitrary prose interpretation.

## Files to Change

| Path | Change |
|---|---|
| install.sh | Modify |
| tests/test-factory-auth.sh | Modify |
| tests/test-state-dir.sh | Modify |
| agents/nightshift-architect.md | Modify |
| agents/nightshift-engineer.md | Modify |
| agents/nightshift-run-all-tests.md | Modify |
| agents/nightshift-spec-writer.md | Modify |
| commands/nightshift-adversarial.md | Modify |
| commands/nightshift-batch.md | Modify |
| commands/nightshift-deploy.md | Modify |
| commands/nightshift-drift.md | Modify |
| commands/nightshift-eng.md | Modify |
| commands/nightshift-implement.md | Modify |
| commands/nightshift-product.md | Modify |
| commands/nightshift-qa.md | Modify |
| commands/nightshift-review.md | Modify |
| commands/nightshift-spec.md | Modify |
| docs/CONFIGURATION.md | Modify |
| docs/PROJECT-CONTEXT.md | [NEW] Create |
| scripts/nightshift-batch-init.sh | Modify |
| scripts/nightshift-batch-resolve.sh | Modify |
| scripts/nightshift-batch-retro.sh | Modify |
| scripts/nightshift-batch-update.sh | Modify |
| scripts/nightshift-capability.sh | Modify |
| scripts/nightshift-citations-trim.sh | Modify |
| scripts/nightshift-claim-cache.sh | Modify |
| scripts/nightshift-crash-check.sh | Modify |
| scripts/nightshift-factory.sh | Modify |
| scripts/nightshift-lock-field.sh | Modify |
| scripts/nightshift-manifest-validate.sh | Modify |
| scripts/nightshift-preflight-check.sh | Modify |
| scripts/nightshift-project-context.py | [NEW] Create |
| scripts/nightshift-pw.sh | Modify |
| scripts/nightshift-retry-exhaust.sh | Modify |
| scripts/nightshift-scope-freeze.sh | Modify |
| scripts/nightshift-scope-thaw.sh | Modify |
| scripts/nightshift-spec-digest.sh | Modify |
| scripts/nightshift-state-dir.sh | Modify |
| scripts/nightshift-stop-hook.sh | Modify |
| scripts/nightshift-tdd-integrity-check.sh | Modify |
| scripts/nightshift-tdd-red-lock.sh | Modify |
| scripts/nightshift-tdd-spec-lock.sh | Modify |
| scripts/nightshift-tracker-trim.sh | Modify |
| scripts/nightshift-triage.sh | Modify |
| tests/test-project-context.sh | [NEW] Create |

Existing test fixture dependency lists may require the new shared helper; record
any such scope amendment before editing those files.

## Guardrails

No provider/model defaults or auth changes. No new universal model gate. No paid
API fallback. No claims of complete prose conflict validation from path discovery.
No Coach changes, installation mutation, main promotion, deletion or deployment.

## Model Router

**Decision:** nightshift-architect. Shared context contract and multiple modules.
Provider/model selection remains in routing.json; spec author is codex.

## Sources

Upstream: https://github.com/doctor-ew/nightshift-community/issues/18 (open, read 2026-09-08).

- `scripts/nightshift-state-dir.sh:1-68` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `scripts/nightshift-manifest-path.sh:1-10` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `scripts/nightshift-manifest-validate.sh:1-33` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `scripts/nightshift-capability.sh:1-126` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `agents/nightshift-run-all-tests.md:1-116` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `commands/nightshift-product.md:1-497` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `commands/nightshift-eng.md:1-600` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `commands/nightshift-batch.md:1-286` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `scripts/nightshift-preflight-check.sh:1-291` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `scripts/nightshift-factory.sh:1-385` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.
- `docs/CONFIGURATION.md:1-34` (branch: integration/nightshift, commit: bd47c2ab031d83e011e443c82611983614897935) — existing behavior and compatibility boundary.

## Output contract details

New resolver JSON keys: status (ok/blocked), project (physical absolute path),
conventions (ordered absolute paths, AGENTS.md then CLAUDE.md per ancestor), manifest
(path/null), test_command (string/null), test_command_source (manifest path/null),
convention_policy (runtime_review_required). Blocked results include a typed code.
Root-only/shell errors print diagnostics to stderr and no successful stdout.
Semantic lookup JSON: status (available/unavailable/error), operation
(document-read), tool (string/null); errors carry a typed code. Unknown operations,
invalid mappings and invalid tool inventories exit 64; unavailable exits 1.

## Scope amendment — installed context availability

Independent source review approved adding install.sh before its modification.
Install the shared policy at docs/nightshift-project-context.md under the runtime
home, and the resolver beside legacy shell adapters. Runtime instructions name
the installed policy/helper explicitly. Fix the existing Bash 3.2 empty UPDATE_ARGS
expansion because it blocks both installed-runtime verification modes. This is a
compatibility repair, not permission to reinstall an active user runtime.
Source: install.sh:437-486,561-565 at baseline bd47c2a.

## Fixture amendment — physical temporary roots

Independent diagnosis identified two existing tests comparing logical temporary
paths against the newly specified physical paths. Canonicalize each TMP_ROOT with
pwd -P after mktemp; preserve every auth/state assertion. No behavior expectation
is weakened. The new resolver suite separately exercises physical alias equality.
