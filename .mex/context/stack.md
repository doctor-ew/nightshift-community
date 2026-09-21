---
name: "stack"
description: "Verified tooling inventory and explicit gaps."
triggers: ["runtime", "dependency", "technology"]
edges: [{"target": "context/setup.md", "condition": "when preparing tools"}, {"target": "context/decisions.md", "condition": "when selecting alternatives"}, {"target": "context/conventions.md", "condition": "when changing a shared role"}]
grounds_to: []
last_updated: "2026-09-20"
mex:
  id: mx_01M21Z3AV2M2XQ83MT8FJBXV8C
  type: architecture
  status: promoted
  revision: 3
  title: stack
  relations:
    - type: related_to
      target: mx_01M21Z3AT5N7R4NW7K2G93Q8K4
      note: when preparing tools
    - type: related_to
      target: mx_01M21Z3AH9N1C5JA0SSQX67SPF
      note: when changing a shared role
---

# Stack

## Core Technologies
Bash is a system executable used for supporting scripts and installer invocation, not a package-manifest dependency. Sources: `scripts/nightshift-update.py` (line 104), `scripts/nightshift-update.py` (line 191).

- **Python** — setup, update, proof-accounting, and trajectory tools. Sources: `scripts/nightshift-setup.py` (line 1), `scripts/nightshift-retry-budget.py` (line 139).
- **Markdown and JSON/TOML** — stage instructions, state records, and configuration. Sources: `AGENTS.md`, `scripts/nightshift-setup.py` (line 20), `scripts/nightshift-trajectory.py` (line 42).

## Standard-library modules and dashboard tooling
Python’s standard-library `tomllib` module supplies the TOML parser imported by setup; it is not a separately installed package. Source: `scripts/nightshift-setup.py` (line 7).

- **unittest / unittest.mock** — setup and release fixtures use Python's standard test framework. Sources: `tests/test-setup-ux.py` (line 16), `tests/test-release-inputs.py` (line 8).

Python’s Unix standard-library `fcntl` module supplies advisory file locks to the update CLI; it is not a separately installed package. Source: `scripts/nightshift-update.py` (line 166).

- **[TO DETERMINE] dashboard dependencies and build tool** — the brief provides no manifest or package manager; hydrate its build configuration before prescribing commands.

## What We Deliberately Do NOT Use
- No gstack commands or agents inside nightshift workflows. Source: `AGENTS.md`, Project conventions.
- No provider-specific tools or static model keys in runtime-neutral role prompts; routing belongs in `routing.json`. Source: `AGENTS.md`, Project conventions.

## Version Constraints
[TO DETERMINE] declared minimum runtime versions: the brief has no manifest/version constraints. Setup directly imports `tomllib` (`scripts/nightshift-setup.py` (line 7)); confirm the supported Python version from project installation evidence before publishing a minimum.
