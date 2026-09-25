---
name: change-cli-runtime
description: Change launcher selectors and runtime defaults without changing ticket identity or role routing.
triggers: ["CLI", "runtime", "model alias"]
edges:
  - target: context/setup.md
    condition: when configuring consumer or global defaults
  - target: context/conventions.md
    condition: when verifying a launcher change
grounds_to: []
last_updated: "2026-09-25"
mex:
  id: mx_01M3024GD90Y8AHCKZVBHZGR9G
  type: pattern
  status: promoted
  revision: 3
  title: change-cli-runtime
  relations:
    - type: related_to
      target: mx_01M21Z3AT5N7R4NW7K2G93Q8K4
      note: when configuring consumer or global defaults
    - type: related_to
      target: mx_01M21Z3AH9N1C5JA0SSQX67SPF
      note: when verifying a launcher change
---

# Change CLI runtime selection

## Context
Inspect the factory parser and runtime settings resolution, setup validation,
and CLI fixtures. Sources: `scripts/nightshift-factory.sh:122`,
`scripts/nightshift-factory.sh:230`, `scripts/nightshift-setup.py:51`,
`tests/test-factory-cli.sh:1`.

## Steps
1. Preserve file paths, spaces, ticket identity, and batch arguments when stripping selectors.
2. Resolve explicit flags before shorthand; resolve project model settings before global settings. Associate legacy `runtime.model` with the provider in its originating settings.
3. Keep alias mappings in configuration. The bundled alias is overridden by global and consumer settings.
4. Keep factory runtime selection distinct from configured role routing.
Sources: `scripts/nightshift-factory.sh:146`, `scripts/nightshift-factory.sh:230`, `scripts/nightshift-factory.sh:255`.

## Gotchas
- A path such as `codex/prompt.md` must remain a file input, including when `--project` follows it.
- Merging global and project dictionaries before interpreting a legacy model can attach it to the wrong provider. Resolve model precedence using each original settings object.
- Match live probes to the actual factory sandbox policy. Local models requested escalation in restricted probes, but both bundled aliases passed shell-tool checks under the default factory policy. Keep the difference explicit. Source: `docs/CLI-RUNTIME-VERIFICATION.md`.
- CLI fixtures copy runtime scripts to a temporary installation and invoke its symlink entrypoint. The updater runs with network sync disabled; locks and all fixture writes stay in the temporary tree. Release selection and update contention remain covered separately by the release tests.
Sources: `tests/test-factory-cli.sh:1`, `tests/test-release-inputs.py:77`.

## Verify
- Run the CLI, factory-auth, and factory-preflight shell fixtures; run setup and release Python tests and ShellCheck on changed shell files.
- Distinguish captured provider argv tests from actual model execution and end-to-end workflow quality.
Sources: `tests/test-factory-cli.sh:1`, `tests/test-factory-auth.sh:1`, `tests/test-factory-preflight.sh:1`, `tests/test-setup-ux.py:16`, `tests/test-release-inputs.py:18`.

## Debug
Check the selected provider/model, original project/global settings, and the admission receipt before changing provider dispatch. Never add a silent fallback to hide failure. Source: `scripts/nightshift-factory.sh:230`.

## Update Scaffold
Update setup context and this pattern when selector semantics or configuration precedence changes. Exact graph grounding is not established for this entry: the impact resolver reported a stale source corpus during this change; the source references above were read directly.

## Advisory commands
Advisory mode must bypass factory ticket admission and automatic setup, reject
push/PR flags, suppress the dashboard, and load the canonical command directly.
Keep consultations read-only; architecture/UX may write their scoped planning
artifacts. Test arbitrary question arguments and empty help, including local aliases
and Claude tools. Sources: `scripts/nightshift-factory.sh`, `tests/test-factory-cli.sh`.

Install shared command documents for every runtime, as well as Claude slash-command
links where selected. The Codex skill resolves `~/.nightshift/commands` with a
source-checkout fallback. Sources: `scripts/nightshift-install-inventory.py:90`,
`skills/nightshift/SKILL.md:28`. Verify actual links as well as inventory generation.

## Output presentation
The launcher wraps engineering/advisory runs with `scripts/nightshift-output.py`.
Per-run output overrides environment, project, user config, then concise default.
Use verbose in argv/admission fixtures that assert raw text. Concise/quiet use
structured provider events; preserve provider exit codes and show semantic error
results even when the process exits zero. Logs remain private and are not removed.
Sources: `scripts/nightshift-output.py`, `tests/test-output.py`,
`tests/test-factory-cli.sh`. Keep presentation separate from explain search scope.

## Initialization boundary
`init` is administrative: bypass the output wrapper and updater just like setup.
Keep config writes delegated to setup's `--defaults` mode. Never initialize a new
project as a side effect of explaining a baseline error. Test init in temporary
folders; preserve the user's real runthrough folder for their own invocation.
Sources: `scripts/nightshift-factory.sh`, `scripts/nightshift-init.py`, `tests/test-init.py`.

## Claude streaming
Claude print mode uses stream-json and verbose in every output mode; the output
helper renders text/tool blocks for verbose users and retains raw events in logs.
Pass canonical command and script paths to the inner worker to avoid installation
searches. Sources: `scripts/nightshift-factory.sh`, `scripts/nightshift-output.py`,
`tests/test-output.py`, `tests/test-factory-auth.sh`.

## Workshop isolation and accounting

The classroom profile uses `nightshift-workshop.py`, not an unbounded factory agent.
Use Claude `--safe-mode` as well as tool/MCP restrictions: `--setting-sources` alone
does not disable personal CLAUDE.md discovery. API calls also use `--bare`.
The retained pilot exposed a personal instruction entering a generated prompt before
this correction; it is not passing evidence. See `docs/WORKSHOP-VERIFICATION.md`
for the final measured outcome and all development attempts. Persist call reservations
before launch; do not reset failed-run budgets or count a spec-phase exit as completion.

Final macOS safe-mode pilot: 17 calls, 43,793 tokens, $0.257202 reported subscription
cost estimate, eight public cases passed. All eight development trials are accounted
for separately in `docs/WORKSHOP-VERIFICATION.md`; interrupted usage is explicitly
unknown where a receipt is absent. Source tests and installed runtime tests pass.

Portal consumers must use the shared routing resolver with the ticket worktree as explicit project context. Do not assume a consumer has `routing.json`; retain the admitted path for asynchronous workers. Sources: `scripts/nightshift-console-chat.py`, `scripts/nightshift-routing-path.py`, `tests/test-console-chat.py`.

For semantic recovery, keep operator authority and test outcomes in the controller. Build bounded evidence packets from verified source and actual outputs; cache by obligation and authorized session. Never turn missing context into an approval or duplicate allowance. The same CLI/browser operation and explicit deployment limits are documented in `docs/DECISION-RECOVERY.md`.
