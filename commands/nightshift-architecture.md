---
name: nightshift-architecture
description: "Record architecture decisions that feed the verified specification."
argument-hint: "[request, task-key, or artifact path]"
---

# Nightshift architecture

This workflow may write only the planning artifacts specified below. It must not start engineering or change gate state.

Read the request, repository instructions, existing brief/PRD/spec and relevant code. Resolve the task's existing docs directory from its tracker and identity; preserve its upstream reference and local bead identity. For an unticketed brief, use docs/planning/<brief-stem>/; if no stable brief or task identity exists, ask for a descriptive name before writing. Never treat a raw ticket reference or arbitrary input as a filesystem path.

Write or update only ARCHITECTURE.md in that directory. Preserve existing decisions and identify revisions. Include: source references; requirements and constraints; system boundaries and interfaces; relevant data flows; alternatives and tradeoffs; chosen and proposed decisions with status; migration/compatibility and failure handling; verification strategy; unresolved questions. Verify named code identifiers against the repository. Do not invent requirements to fill gaps.

Finish with the artifact path and next spec command. The product/spec stage must consume this document as planning input, verify its claims and incorporate accepted decisions into SPEC.md. It does not replace SPEC.md, unlock implementation, satisfy adversarial verification, or update gate status. Do not write implementation code or mutate tickets, branches, trackers, or review receipts.
