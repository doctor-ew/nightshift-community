# Scoped legacy-brand and provider-coupling regression guard

Status: proposed; independent review required before implementation.
Dependency: issue 18 integrated through PR #24; sources re-grounded at the integration revision below.
Implementation baseline: integration/nightshift at 20aefa116003134f6464b2673ab11f8a06e9e353.
Delivery: integration/nightshift PR. No active installation or Coach changes.

## Solution

Extend the existing branding regression with one reusable, read-only scanner and one shared installer inventory module. The scanner independently reports maintained public source and installed Nightshift-owned artifacts. It detects explicit retired-name and provider-coupling patterns, with precise reviewed exceptions. It is a bounded static regression guard, not a complete natural-language classifier or historical cleanliness audit.

Proposed new files and interfaces (not existing APIs):

- `scripts/nightshift-install-inventory.py`: shared pure inventory module; command interface accepts `--project DIR --runtime codex|claude|local|all --target DIR --codex-target DIR --nightshift-target DIR --bin-target DIR`. Default output is a JSON inventory; `--nul` emits category, kind, source, destination records separated by NUL for installer consumption. Category preserves installation ordering; kind distinguishes file/tree operations. No shell text generation or eval.
- `scripts/nightshift-branding.py`: `--project DIR --inventory source|installed|all`, with the same target/runtime arguments for installed inventory. JSON output only. The source-only default does not discover or read user homes. Installed/all require explicit target arguments, supplied by installer after its existing defaults are resolved.
- `scripts/nightshift-branding-policy.json`: reviewed exact exceptions, shipped by the same inventory module; finite rule definitions remain in the scanner. No policy file may authorize arbitrary filesystem paths.

Both Python entrypoints use only the standard library. Suppress bytecode writes before importing the inventory module. Installed copies must work without Git metadata or access to an original checkout; scan source is explicitly the checkout supplied to the installer audit, not an inferred user repository.

## Shared installation ownership

The inventory module becomes the single owner of the file/tree mappings currently implemented by install.sh loops. Installer install operations and scanner classification consume this module; do not preserve a second independent destination list in the scanner. Leave backups, repair decisions, hook migration, auth configuration, and update configuration in install.sh. Preserve order and runtime selection, including local using the Codex skill.

Exact mapping families from the current installer:

| Source relative to project | Destination relative to selected root |
| --- | --- |
| commands/*.md | Claude target: commands/<basename> |
| scripts/*.sh | Nightshift target: scripts/<basename>; Claude target: scripts/<basename> |
| scripts/nightshift-*.py | Nightshift target: scripts/<basename> |
| scripts/nightshift-project-context.py | Claude target: scripts/nightshift-project-context.py |
| docs/PROJECT-CONTEXT.md | Nightshift target: docs/nightshift-project-context.md |
| scripts/nightshift-contract.jq | Nightshift and Claude targets: scripts/nightshift-contract.jq |
| contracts/nightshift-*.schema.json | Nightshift and Claude targets: contracts/<basename> |
| agents/*.md | Nightshift and Claude targets: agents/<basename> |
| routing.json | Nightshift target: routing.json; Claude target: nightshift-routing.json |
| nightshift.toml | Nightshift target: nightshift.toml |
| dashboard/dist tree and dashboard/server.py, when dist exists | Nightshift target: same relative paths |
| skills/nightshift tree | Codex target: skills/nightshift |
| scripts/nightshift-factory.sh | Bin target: nightshift |
| proposed scanner policy JSON | Nightshift target: scripts/<same basename> |

The inventory module explicitly includes both new Python helpers through the existing prefixed helper family. The scanner, inventory module and policy are installed together in shared scripts; legacy adapters use the separately installed project-context helper and do not import the scanner, so no additional legacy scanner/policy copies are required. Each tree's descendants are enumerated safely for scanning; symlink installation still uses the tree operation. Validate name/namespace requirements before installation. Preserve the existing launcher, routing, manifest and skill directory names as intentional mappings.

Reuse install-links.json as ownership evidence. Validate JSON shape, duplicate keys, size, destination membership, and source equality against the current shared inventory before accessing any listed target. Reject forged external entries without following or printing their targets. Do not trust the manifest to introduce mappings. An exact regular-file copy requires a valid matching ownership record; changed content must still be scanned. An exact symlink to its expected declared source can independently prove ownership when a repair omitted its record. Missing ownership for an existing regular copy is incomplete coverage, never permission to inspect it.

Tree installations have one install-links.json entry for the tree root. Child ownership derives from that validated root and shared source-relative mapping, with containment checks on each descendant; children do not require separate ownership records.

Routing and manifest contents are user-maintained after installation; the audit only reads exact mapped owned files, never linked resources or secret/config references within them. Missing records remain visible. No ownership is inferred from a basename or a shared directory alone.

## Scan boundaries and coverage

Source inventory includes these exact maintained root files: README.md, CLAUDE.md, AGENTS.md, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE, VERSION, .gitignore, install.sh, routing.json, nightshift.toml. Include descendants of scripts/, commands/, agents/, skills/, tests/, docs/, contracts/, evals/, dashboard/, and .github/. Exclude dashboard/node_modules/, all __pycache__ directories, and compiled Python bytecode; declare these exclusions. Include dashboard/dist text, nested docs, and generated fixture declarations in test source. Do not read .git, local .nightshift.toml, runtime state, backups, credentials, unrelated homes, or history. Missing required source roots/files and unreadable/undecodable source artifacts are coverage failures. Optional generated dashboard/dist absence is reported as not installed, not an error. Retained task documentation is in scope; historical mentions need precise exceptions rather than excluding all ticket docs.

Scan source paths only after checking ancestor and leaf symlinks for containment within the explicit physical project. Discover without following directory symlinks; validate them separately before traversal. External links, cycles, unreadable directories, and unsupported objects produce coverage diagnostics. Never silently skip a decode failure.

Installed audit inspects only shared inventory destinations and authorized owned tree descendants. Validate target-root and ancestor links before reads; a configured root may be canonicalized explicitly, but a link inside that root must not escape the approved mapping. Validate every nested link and require exact expected source correspondence, not merely membership somewhere in the checkout. Record missing, unknown ownership, dangling, external, unreadable and invalid-encoding outcomes separately. Do not list or inspect unrelated siblings, settings.json, hooks.json, provider homes, configuration values outside mapped artifacts, or .backup trees.

A wholly absent installed inventory is reported unavailable with non-success for an installed/all request. Source-only CI can pass independently. This intentional --check behavior makes a fresh, uninstalled target distinguishable from a complete installed audit.

## Detection and precise exceptions

Retired branding rules apply to relative filenames and file content in both inventories. Use case-insensitive patterns assembled from `"cx" + "eng"`, `"con" + "nexure"`, `"drew" + r"[-_ ]pipeline"`, and `"drew" + "-"`; add the retired slash-command family assembled from `"/" + "cx"` with a command boundary and optional hyphenated command suffix, and the targeted ADR form assembled from `"CX" + " ADR-002"`. Assemble banned fixture literals from fragments so scanner fixtures do not themselves fail the maintained-source audit. No broad ban on the letters CX.

Provider-coupling checks apply to canonical commands/roles and core scripts: explicit provider MCP invocation names, hardwired executor directives, static role model frontmatter, and direct legacy project-variable/convention resolution outside the shared issue 18 boundary. Detect a finite documented list of patterns and known variants; do not claim arbitrary prose interpretation. Frontmatter checks distinguish actual keys from explanatory comments. Match affirmative execution patterns without flagging prohibitions such as “Do not invoke gstack.”

Issue 18 permits legacy inputs only through scripts/nightshift-project-context.py and documented compatibility readers; it permits actual adapter routing/auth in existing dispatch infrastructure. Its document capability asks adapters for actual tool mappings, with no provider MCP identifier in core. Its legitimate role prose mentions both applicable convention files. Preserve these exact contexts. The `env -u CLAUDE_PROJECT_DIR` operation in `scripts/nightshift-preflight-check.sh:193` clears the legacy variable at the batch boundary; it is an anticipated exact compatibility exception, not direct legacy project resolution.

The policy schema is exactly `{ "version": 1, "exceptions": [{ "rule": "...", "path": "...", "context": "...", "reason": "..." }] }`; reject unknown keys, invalid types and unsupported versions. `rule` must be one of `retired-brand`, `provider-mcp`, `provider-executor`, `role-model`, `legacy-project-context`, or `legacy-convention`. These finite rule definitions live in the scanner, not configurable expressions in policy. `path` is an exact repository-relative path; `context` is the exact matching source line (or exact relative path for a filename finding); `reason` is a nonblank review rationale. Validate duplicate and unused entries against source inventory. Do not use provider-name exemptions, path-prefix exemptions, whole-script exceptions, or automatic baseline acceptance. Context assertions fail when installed text changes even if its source path is allowed. Installed policy classification uses the validated source mapping, not the installed basename. Exact documented negative examples in docs may be excepted with rationale; test fixtures must verify that nearby unrelated occurrences still fail.

## Output contract

Proposed JSON result keys: status, inventories, findings, coverage. Each finding contains keys `inventory`, `rule`, `path` (relative logical path), and `line`; path-only findings use line 0. Coverage records contain inventory, logical path and a fixed reason code. Counts distinguish discovered/scanned/missing/unreadable/unknown/excluded. Exit 0 means requested coverage is complete and no findings; exit 1 means findings or coverage failure; exit 64 means invalid arguments/policy.

Never print matching text, exception context, arbitrary exception messages, absolute user paths, symlink target values, credentials, or content-derived diagnostics. Encode control characters in names as JSON escapes. Artifact reads are capped at 4 MiB; ownership records and policy are capped at 1 MiB each. Enforce caps with bounded reads even if size metadata changes. Oversize artifacts or ownership records produce coverage failure, not truncated clean scans; oversized policy is invalid policy (exit 64).

## Installer and CI integration

Immediately after existing argument/runtime/auth validation and destination calculation (after install.sh baseline line 101, before all display/dependency/conflict sections), ACTION=check calls the scanner with all inventory and exits with its result before dependencies, mkdir, conflicts, hook checks, archive/migration, update setup, or writes. This early branch exits before the existing conflict-section mkdir; remove the obsolete late --check branch. Update help to describe the structured scoped audit and fresh-target non-success. Do not make normal installation mutate or audit unrelated user settings beyond its pre-existing behavior.

Extend tests/test-branding.sh to call the same scanner, preserve existing alias-preservation fixtures, and test temporary copy/symlink installs. Existing CI discovery in .github/workflows/shellcheck.yml already executes this test; no second workflow is needed.

## Acceptance criteria and fixtures

1. Separate source and installed reports detect banned names in paths/content, nested maintained docs, and installed drift with exact logical file/line, no content output.
2. Core MCP directives, hardwired provider executors and role model keys fail. Real routing/auth/adapter and issue 18 compatibility contexts pass only under precise policy. Prohibition/comments and affirmative execution have distinct fixtures.
3. Source symlink escape, installed ancestor/nested escape, loops, dangling links, unknown copies, unreadable files and invalid encodings never produce clean coverage. External target sentinels prove no reads.
4. Valid installer ownership maps cover all runtime choices and both copy/symlink mode; malformed, forged, duplicate and omitted records are tested. Extra unrelated sibling plugins/settings with sentinels remain unread and unchanged.
5. The shared mapping is actually consumed by installer and scanner. New Python/policy dependencies are installed. Snapshot source and installed expected mappings to assert correspondence without duplicating implementation destination rules in production.
6. --check on fresh and existing targets performs no filesystem writes, cache creation, dependency/provider launch, hook reads, installation or repair. Instrument opens and compare before/after trees; absence of mutations alone does not prove absence of reads.
7. Oversized files, sensitive sentinel lines and control-character filenames produce sanitized deterministic output and explicit failures.
8. Focused branding/installer regressions, shellcheck and existing offline regression harness pass. Preserve issue 18 context and factory tests. Sandbox-required test execution remains an environmental permission request, not a stage waiver.

## Files to Change

| File | Change |
| --- | --- |
| scripts/nightshift-install-inventory.py | [NEW] Add proposed shared mapping module/CLI |
| scripts/nightshift-branding.py | [NEW] Add proposed scanner/CLI |
| scripts/nightshift-branding-policy.json | [NEW] Add proposed precise rules/exceptions |
| install.sh | Consume shared mapping; early read-only check |
| tests/test-branding.sh | TEST: Extend focused regressions and existing source gate |
| docs/BRANDING-AUDIT.md | [NEW] Document audit boundaries, outputs and exclusions |
| docs/19/SPEC.md | Add reviewed specification after worktree creation |

The existing docs/SCOPED-VERIFIER.md describes subprocess authorization and remains unchanged; proposed docs/BRANDING-AUDIT.md owns this audit documentation. No routing changes, provider calls, history rewrites, active runtime installation, or Coach changes. Do not expand this into a general installer redesign. Keep installer operation helpers and mutation policy intact.

## Model Router

Decision: nightshift-architect. Shared ownership contract, symlink boundary and installer integration span multiple modules. Provider/model selection remains in routing.json. Spec author: codex. Independent cross-provider review must inspect the ownership and privacy boundaries before implementation.

## Sources

Upstream: https://github.com/doctor-ew/nightshift-community/issues/19 — scoped acceptance, integration-only delivery and prohibited runtime/Coach mutation; read 2026-09-08.

All repository citations below refer to branch integration/nightshift, commit 20aefa116003134f6464b2673ab11f8a06e9e353. They describe the committed baseline, not concurrent issue 19 fixture edits.

- `install.sh:24-105` — selected roots and source/destination definitions.
- `install.sh:130-179` — install_one/install_tree, repair omissions and tree-level ownership pairs.
- `install.sh:295-348` — current conflict directory creation, hook reads and late --check exit.
- `install.sh:433-490` — shared and Claude mappings, including project-context documentation and legacy Python helper.
- `install.sh:555-580` — Codex skill tree, launcher, update configuration and install-links.json persistence.
- `tests/test-branding.sh:9-30` — original retired fragments and incomplete source inventory.
- `tests/test-branding.sh:32-49` — original alias-preservation installation fixture.
- `docs/PROJECT-CONTEXT.md:1-75` — integrated physical identity, convention review, compatibility and optional capability boundaries.
- `agents/nightshift-run-all-tests.md:20-37` — legitimate convention prose and installed documentation/helper dependencies.
- `commands/nightshift-product.md:189-197` — neutral document capability consumer and optional fallback.
- `.github/workflows/shellcheck.yml:27-41` — offline harness, shellcheck and behavioral regression discovery.
- `routing.json:124-145` — architect role routing.
- `routing.json:170-186` — independent cross-provider review policy.

## Shared module data contract

Proposed function `make_inventory(project, runtime, targets)` returns a dict with
version 1 and entries. targets has keys claude, codex, nightshift, bin with explicit
root paths. Each entry has category, kind (file/tree), source (absolute path),
destination (absolute path), source_relative (repository path), and logical_path
(root label plus root-relative destination). Categories are claude_commands, shared,
shared_roles, claude_adapters, codex_skill, launcher. No file reads or writes occur
except source directory enumeration; no arbitrary ownership record influences mappings.
The scanner imports this function with bytecode disabled. Installer computes the
JSON once, then selects categories through jq to feed NUL-delimited install_one or
install_tree calls. Existing mutation helpers and operation ordering remain unchanged.
