---
name: "setup"
description: "Verified local commands and setup evidence gaps."
triggers: ["setup", "install", "environment"]
edges: [{"target": "context/stack.md", "condition": "when checking runtime support"}, {"target": "context/updates.md", "condition": "when maintaining an installed checkout"}, {"target": "patterns/preserve-setup-files.md", "condition": "when editing setup persistence"}]
grounds_to: []
last_updated: "2026-09-20"
mex:
  id: mx_01M21Z3AT5N7R4NW7K2G93Q8K4
  type: guide
  status: promoted
  revision: 4
  title: setup
  relations:
    - type: related_to
      target: mx_01M21Z3AV2M2XQ83MT8FJBXV8C
      note: when checking runtime support
    - type: related_to
      target: mx_01M21Z3AW1PMP70S4G96GA2Q1P
      note: when maintaining an installed checkout
    - type: related_to
      target: mx_01M21Z3AZH1PBP57Q1V725EMEY
      note: when editing setup persistence
---

# Setup

<!-- mex:entity
id: mx_01M21Z3AS90DAYCZY9CPF11CP5
type: guide
status: promoted
revision: 1
-->
## Prerequisites
- Python with the imported `tomllib` module available. Source: `scripts/nightshift-setup.py` (line 7).
- Git and Bash for the update/factory path. Source: `scripts/nightshift-update.py` (line 156), `scripts/nightshift-update.py` (line 191).
- [TO DETERMINE] complete install prerequisites and supported provider CLI versions: the brief does not provide them.

<!-- mex:entity
id: mx_01M21Z3ARC4J66GF6H7JQWNV40
type: guide
status: promoted
revision: 1
-->
## First-time Setup
1. [TO DETERMINE] canonical clone/install invocation; obtain the pilot quickstart cited in the setup brief before prescribing installation flags.
2. From the target project, use `nightshift setup` interactively. Source: `scripts/nightshift-setup.py` (line 64).
3. Read the resulting configuration with `python3 scripts/nightshift-setup.py --project . --read` from this source checkout. Source: `scripts/nightshift-setup.py` (line 12), `scripts/nightshift-setup.py` (line 60).
4. [TO DETERMINE] end-to-end provider login and first-ticket verification; the brief explicitly says fresh-machine validation is still required.

<!-- mex:entity
id: mx_01M21Z3AQGAFGTJBYFKPJSBS6K
type: guide
status: promoted
revision: 1
-->
## Environment Variables
- **Required:** [TO DETERMINE] the full runtime/adapter environment contract is not in the supplied brief or hydrated nodes.
- **Conditional:** [TO DETERMINE] ticket-provider credentials; hydrate each adapter before documenting names.
- **Optional `NIGHTSHIFT_SYNC_CHECK`** — update CLI run-path switch. Source: `scripts/nightshift-update.py` (line 171).
- **Optional `NIGHTSHIFT_HOME`** — release tests override it to isolate runtime storage. Source: `tests/test-release-inputs.py` (line 23).
- **Internal `NIGHTSHIFT_UPDATE_GUARD`** — passed to the factory child by the updater; not a secret value. Source: `scripts/nightshift-update.py` (line 190).

<!-- mex:entity
id: mx_01M21Z3APN7S6YPQYXA83ZHSX7
type: guide
status: promoted
revision: 1
-->
## Common Commands
- The launcher accepts `nightshift prompt.md`, `nightshift codex prompt.md`, `nightshift codex/qwen bd:bead-123`, and `nightshift codex/devstral prompt.md`. The bundled aliases select Codex through Ollama with `qwen3-coder:30b` and `devstral-small-2:24b`; project/global configuration can override them or add more. Sources: `scripts/nightshift-factory.sh` (line 123), `scripts/nightshift-factory.sh` (line 231), `nightshift.toml` (line 18).
- Runtime shorthand chooses the factory worker, preserving configured role routing. Per-runtime defaults live in `runtime.models`; `runtime.aliases` maps aliases to provider/model pairs. Sources: `scripts/nightshift-factory.sh` (line 238), `scripts/nightshift-setup.py` (line 51).
- `nightshift setup` — interactive configuration. Source: `scripts/nightshift-setup.py` (line 64).
- `python3 scripts/nightshift-setup.py --project . --read` — read configuration JSON. Source: `scripts/nightshift-setup.py` (line 12), `scripts/nightshift-setup.py` (line 60).
- `python3 tests/test-setup-ux.py` — setup regression fixtures. Source: `tests/test-setup-ux.py` (line 16); invocation verified during scaffold population.
- `python3 tests/test-release-inputs.py` — release and local-input fixtures. Source: `tests/test-release-inputs.py` (line 145).
- `python3 evals/trajectory/replay.py` — trajectory comparison entry point. Source: `evals/trajectory/replay.py` (line 16).
- Dev server, linter, build: [TO DETERMINE] exact project-supported commands; brief tooling fields are null.

<!-- mex:entity
id: mx_01M21Z3ANSQKZZ7ZD6RQX39RTZ
type: guide
status: promoted
revision: 1
-->
## Common Issues
- Both bundled local models passed bounded shell-tool smoke tests under the default factory policy. Restricted standalone sandbox probes failed by requesting escalation under approval-never; do not equate these results with full-ticket quality or restricted-mode readiness. Evidence: `docs/CLI-RUNTIME-VERIFICATION.md`.
- **Dirty/development checkout update deferral:** covered by release fixtures; retain local work and inspect update context. Source: `tests/test-release-inputs.py` (line 48), `tests/test-release-inputs.py` (line 70).
- **Adapter repair failure:** release fixtures assert a retained pending receipt; inspect installer error before retrying. Source: `tests/test-release-inputs.py` (line 89).
- These are regression-covered failure boundaries, not claims of historical production incidents.

## Display preference
Save `[output]` with `mode = "concise"`, `"verbose"`, or `"quiet"` in user or
project `.nightshift.toml`. Per-run `--output` overrides `NIGHTSHIFT_OUTPUT`, project,
user, then concise default. `NIGHTSHIFT_HOME` relocates user configuration and
private logs. Sources: `scripts/nightshift-output.py`, `scripts/nightshift-setup.py`.

## Explicit project initialization
`nightshift init` fills missing defaults through setup, initializes Git if absent,
and commits configuration plus explicitly included starter files. It does not run
models. Supports a directory, runtime selector, and repeatable `--include FILE`.
Existing staged work or edits to selected initialization files block it. Source:
`scripts/nightshift-init.py`, `scripts/nightshift-setup.py`, `tests/test-init.py`.
