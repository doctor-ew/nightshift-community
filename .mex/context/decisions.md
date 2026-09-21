---
name: "decisions"
description: "Documented architectural constraints without invented history."
triggers: ["decision", "why", "alternative"]
edges: [{"target": "context/architecture.md", "condition": "when evaluating component boundaries"}, {"target": "context/stack.md", "condition": "when evaluating tooling"}]
grounds_to: []
last_updated: "2026-09-08"
---

# Decisions

## Decision Log

<!-- mex:entity
id: mx_01M21Z3AM218WSWVPY78T0MX04
type: decision
status: promoted
revision: 1
-->
### Runtime-neutral core
**Date:** [TO DETERMINE] original adoption date; requires relevant commit history.
**Status:** Active
**Decision:** Keep canonical stage instructions and roles independent of runtime adapters.
**Reasoning:** Codex, Claude, and local runners must share artifacts, routing, and policy.
**Alternatives considered:** [TO DETERMINE] no historical evaluation was supplied.
**Consequences:** Provider-specific routing stays outside role prompts.
Source: `AGENTS.md`, Using the pipeline and Project conventions.

<!-- mex:entity
id: mx_01M21Z3AK61KTR4B3HR7AB2MGA
type: decision
status: promoted
revision: 1
-->
### Beads remains local
**Date:** [TO DETERMINE] original adoption date; requires relevant commit history.
**Status:** Active
**Decision:** Mirror upstream tickets into beads without making beads authoritative.
**Reasoning:** The workflow accepts multiple upstream ticket systems.
**Alternatives considered:** [TO DETERMINE] no historical evaluation was supplied.
**Consequences:** Preserve upstream task identity and internal bead identity separately.
Sources: `AGENTS.md`, Project conventions; setup brief, README excerpt.

<!-- mex:entity
id: mx_01M21Z3AJB68PYV6QS8AJ3VNSR
type: decision
status: promoted
revision: 1
-->
### Keep the installed source checkout
**Date:** [TO DETERMINE] original adoption date; requires relevant commit history.
**Status:** Active
**Decision:** A symlink installation keeps its nightshift checkout as upgrade source.
**Reasoning:** The installation deliberately uses that checkout for upgrades.
**Alternatives considered:** [TO DETERMINE] no installation tradeoff history was supplied.
**Consequences:** Do not remove the checkout after installation; consult update context before changing release behavior.
Source: `AGENTS.md`, Using the pipeline.
