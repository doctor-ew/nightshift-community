# Architecture decision enforcement and routing evaluation

## Status and scope

Proposed extension to the existing controller; not implemented or accepted by this document. All UI scope remains. Codex remains the primary provider, with explicit Claude delegation. Existing repositories, ticket evidence, decisions, and retry allowances must be preserved.

## Problem

A corrected implementation can regress on a later ticket when a worker treats historical prose or generic design advice as authority. An attestation that a convention was checked is not evidence that the resulting code complies. Routing to a different model does not resolve policy precedence.

## Smallest structural change

Extend the existing decision record and handoff, rather than introducing a second policy platform. A project-scoped accepted decision needs its applicability, authoritative operator provenance, accepted reference implementation, superseded decisions, and concrete constraints. Ticket-scoped findings remain separate. Explicit operator changes can supersede a decision; a model cannot silently promote historical text or its own review advice into policy.

Resolve applicable decisions before author or reviewer dispatch. Both receive the same resolved policy and reference evidence. Retain obsolete artifacts as history with provenance; exclude their instructions from the active policy. Graph retrieval supplies relevant source and dependency relationships, not authority. A source hash establishes freshness, not whether a decision was approved.

Use existing lint, dependency, or AST tooling to enforce concrete constraints where available. Examples include preventing a specifically rejected dependency or an unauthorized new shared layer within an explicitly scoped template family. Do not use blanket bans on new files, abstraction, or duplication. Necessary reuse and explicitly approved exceptions must remain possible. Semantic disagreements require evidence against the resolved decision, not a generic design principle.

Bind each check result to the ticket, source revision, decision version, check implementation, and actual command outcome. Textual PASS declarations and test-name tags do not establish passing execution. Changed relevant inputs invalidate dependent evidence; unrelated changes must not restart the entire workflow.

## Routing boundaries

Deterministic code decides whether configuration exists, budgets permit dispatch, evidence remains current, checks passed, or manual acceptance is pending. Models may assess semantic questions; they cannot overwrite these facts or reopen settled decisions.

Jev is a candidate for narrow semantic screening, not an authority over routing policy. The current adapter asks whether evidence supports claims and distinguishes observations from limitations; it does not measure architectural compliance or choose a provider. Keep new decision questions in shadow evaluation until held-out results demonstrate value. An uncertain response routes to the existing review path without granting a new allowance.

Apertus 8B is a candidate local classifier or critic. Its quantization quality does not establish coding quality or compliance with accepted architecture. Compare it with deterministic checks, the existing review path, and Jev using the same evidence. Do not download or deploy it as a prerequisite to correcting controller behavior.

## Acceptance experiment

1. Retain a rejected implementation, the accepted correction, and a subsequent sibling ticket. Use private fixtures for private source; use independently authored synthetic examples in the public repository.
2. Record the accepted scoped decision once. Leave conflicting historical Markdown available as test data.
3. Run the next ticket through implementation, review, and repair. The accepted pattern must survive author and reviewer dispatch, including provider changes.
4. Seed a semantic regression, a renamed equivalent, an unrelated change, legitimate shared code, and an explicitly superseded decision. Measure missed regressions and false positives separately.
5. Interrupt and resume. Retain completed work, the same decisions, outstanding findings, next permitted action, and charged attempts. Missing routing must launch no worker. Unchanged inputs must launch no repeated completed review. No configuration question or allowance reset is permitted.
6. Completion requires current passing required checks and an explicit pending manual acceptance state where applicable. A successful worker process is insufficient.

Separate fixture development from held-out evaluation. Record model and prompt versions, input provenance, requests, latency, observed billing, fallback calls, repairs, human rework, and final accepted behavior. Report unknown cost as unknown. A cheap judge is useful only if total accepted-task cost or turnaround improves without unacceptable missed regressions. Do not equate vendor confidence or a numerical score with calibrated probability.

## Foundry and burstable execution

Keep the existing UI over the durable controller. A viable deployment separates three responsibilities: durable orchestration for state transitions and admission; isolated container jobs for repository checkout, generation, build, and tests; Foundry for supported model inference. Short event handlers can use Functions. Avoid making every role a separate service.

Model calls and other external I/O belong in activities or workers, outside deterministic orchestration replay. Persist dispatch identity and spend reservations before requests, and reconcile interrupted calls before retrying. Worker retries must not create new ticket budgets. Durable execution history does not replace semantic ticket evidence.

Evaluate the existing Foundry model router before building a separate learned routing service. Its available model pool and deployment prerequisites must be checked against the actual Azure project. A model endpoint does not automatically reproduce the Codex or Claude agent harness, tools, memory, or filesystem controls. Any learned routing must remain subordinate to the explicit primary/delegate policy.

No Azure resources were provisioned for this assessment. Deployment tooling and project configuration still require verification before a live proof. Rehosting is a later execution adapter, not acceptance evidence for architecture enforcement.

## References

- [Apertus GGUF model card](https://huggingface.co/bartowski/swiss-ai_Apertus-8B-Instruct-2509-GGUF)
- [Jev typed decisions](https://docs.typesafe.ai/introduction)
- [Foundry model router](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router)
- [Durable orchestration constraints](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-code-constraints)
- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
