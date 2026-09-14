---
name: nightshift-explain
description: "Explain a change or run using its actual evidence."
argument-hint: "[request, task-key, or artifact path]"
---

# Nightshift explain

Read-only consultation: do not edit files, run builds/tests, mutate tickets or Git state, or advance engineering gates.

Read the named artifact first. Choose the explanation from the input, not from
an assumption that every request is a completed engineering run.

For a brief or requirements document:
- Lead with its purpose, intended user and deliverable in plain language.
- Summarize the requirements, scope and important choices with source citations.
- Recommend one useful next step proportional to its size. A small brief can go
  directly to nightshift with that brief; do not invent an extra planning gate.
- Add at most one short evidence-status note when relevant: requirements describe
  intended behavior, not proof that implementation exists.
- Stop after the named document and directly relevant references answer the
  question. Do not enumerate unrelated trackers, past failures, proof directories
  or repository history merely to establish that a brief is a brief.

For a run, change, failure, or an explicit audit request:
1. Resolve its task identity and follow associated tracker/artifact links only.
   Use scoped Git diff/status/log when shell access is available. Expand searches
   only when a specific unresolved question requires it. If candidates remain
   ambiguous, list them and ask which one; do not choose by modification time.
2. Explain the intended outcome, actual changes, and important design decisions.
3. Report recorded checks and revision coverage, distinguishing recorded evidence
   from fresh verification. Do not execute tests in this read-only workflow.
4. Identify remaining work and practical consequences, then give one next step.

For BMad output, follow its supplied artifact links with the same scope rules.
Explicit audits may investigate more deeply, but remain tied to the requested
identity. Display verbosity never changes investigation depth or evidence gates.
Keep the response proportional to the input; use file:line citations for claims.

A successful provider exit is not a passing engineering gate. Missing review/proof is unknown, never success. Explain limitations if shell or evidence is unavailable; do not fabricate a diff, receipt, or check result. Keep secrets and private payloads out of the response.
