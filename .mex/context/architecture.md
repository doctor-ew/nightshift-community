---
name: "architecture"
description: "Runtime-neutral pipeline structure and boundaries."
triggers: ["architecture", "pipeline", "integration"]
edges: [{"target": "context/stack.md", "condition": "when selecting tooling"}, {"target": "context/decisions.md", "condition": "when evaluating architectural alternatives"}, {"target": "context/proof-accounting.md", "condition": "when a proof gate cannot admit work"}, {"target": "context/updates.md", "condition": "when updating an installed checkout"}]
grounds_to: []
last_updated: "2026-09-26"
mex:
  id: mx_01M21Z3ACK0HJ2DDGW0YPPAWKR
  type: architecture
  status: promoted
  revision: 4
  title: architecture
  relations:
    - type: related_to
      target: mx_01M21Z3AV2M2XQ83MT8FJBXV8C
      note: when selecting tooling
    - type: related_to
      target: mx_01M21Z3AMXY4C5AAH2N44827A3
      note: when a proof gate cannot admit work
    - type: related_to
      target: mx_01M21Z3AW1PMP70S4G96GA2Q1P
      note: when updating an installed checkout
---

# Architecture

<!-- mex:entity
id: mx_01M21Z3ABHR93SBDHQTTSQS71D
type: component
status: promoted
revision: 1
-->
## System Overview
Ticket references enter through nightshift or a runtime adapter.
Product work produces a spec and, when beads is available, a local beads mirror. Source: `commands/nightshift-product.md`.
Adversarial verification precedes implementation.
Implementation proceeds through spec-lock, RED, red-lock, and GREEN.
Review, drift, QA, preflight, and deploy form subsequent gates.
The orchestrator records resumable progress in `.nightshift/<task-key>.md`.
Commands and role prompts form the runtime-neutral core; runtime adapters expose it.
Source: setup brief in `.mex/local/setup-population-raiHOV/prompt.md`, README excerpt.

<!-- mex:entity
id: mx_01M21Z3AACGERR4NCF231TS3K5
type: component
status: promoted
revision: 1
-->
## Key Components
- **commands/** — canonical stage instructions; depends on the artifacts and supporting scripts. Source: `AGENTS.md`, Project instructions.
- **agents/** — reusable runtime-neutral roles; provider selection belongs in `routing.json`. Source: `AGENTS.md`, Project conventions.
- **scripts/** — supporting pipeline tooling; Python graph evidence includes setup, updates, proof accounting, and trajectory validation. Sources: `scripts/nightshift-setup.py` (line 1), `scripts/nightshift-update.py` (line 126), `scripts/nightshift-retry-budget.py` (line 139), `scripts/nightshift-trajectory.py` (line 42).
- **tests/, evals/, dashboard/** — test/evaluation and dashboard areas identified by the setup brief; detailed server architecture remains [TO DETERMINE] until its implementation is hydrated.

<!-- mex:entity
id: mx_01M21Z3A93K51N9ZY2PV6H0NPG
type: component
status: promoted
revision: 1
-->
## Optional tools and external integrations
Beads (`bd`) is an optional external CLI for the local engineering ledger, not a package-manifest dependency; the upstream ticket remains authoritative. Source: `AGENTS.md`, Project conventions.

- **GitHub, Jira, Monday, Notion** — ticket-source integrations named in the README excerpt; credentials and per-adapter transport details are [TO DETERMINE] pending graph evidence.
- **Codex, Claude Code, local-model runners** — runtime choices sharing artifacts, routing, and policy. Source: `AGENTS.md`, Using the pipeline.

<!-- mex:entity
id: mx_01M21Z3A74RSVTA2D58EPT4YQF
type: component
status: promoted
revision: 1
-->
## What Does NOT Exist Here
- No runtime owns the canonical implementation; adapters wrap the shared core. Source: `AGENTS.md`, Using the pipeline.
- Beads is not an upstream project source of truth. Source: `AGENTS.md`, Project conventions.
- Beginner readiness is not established: the brief's README explicitly requires fresh-machine, independent end-to-end validation.

## Optional planning and consultation
Help, explain, architect/dev/PM/UX consultations, architecture/UX artifact workflows,
and a read-only optional BMad bridge are outside the engineering pipeline.
Architecture/UX artifacts feed product/spec verification; they do not advance gates.
Sources: `commands/nightshift-help.md`, `commands/nightshift-architecture.md`,
`commands/nightshift-ux.md`, `commands/nightshift-bmad.md`,
`commands/nightshift-product.md`, `commands/nightshift-spec.md`.

Intake namespace follow-up: bare GitHub references must match independently derived project-origin identity; qualified references retain explicit repository selection. Existing input/context and journal safeguards remain. Sources: `scripts/nightshift-intake.py`, `tests/test-intake-namespace-review.py`, `docs/operations/INTAKE-NAMESPACE.md`. Synthetic evidence only; no runtime activation.
Operation decision retention: missing referenced question evidence blocks instead of silently disappearing. Current normalized question text reuses settled answers across rationale/options changes and earlier task identities; changed dependency bases remain distinct. Sources: `scripts/nightshift-operations.py`, `tests/test-operation-hitl-additional-review.py`, `docs/operations/DECISION-RETENTION.md`. Synthetic candidate only; no activation.
