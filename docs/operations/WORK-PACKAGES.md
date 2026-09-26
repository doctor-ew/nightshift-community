# Work-package composition

## Contract

`scripts/nightshift-work-packages.py` validates version 1 graphs. Each child references an ordinary operation plan and declares its inputs, owned outputs, interfaces, prerequisites and allowance. The parent declares requirement IDs and aggregate limits. A final integration package depends transitively on every child and covers every parent requirement.

Validation rejects cycles, missing dependencies, overlapping ownership, undeclared cross-package interfaces and insufficient aggregate allocation. Hashes bind referenced plans and input contents. Valid structure is not semantic approval. Templates contain data; they do not carry approvals or allowances.

## Controller candidate

`scripts/nightshift-package-controller.py` composes the existing Groom, Implement, Verify and Review operations in isolated disposable repositories. Preparation uses the ordinary Groom recipe. Its bounded packets include declared child contracts so independent challenge can evaluate semantic coverage. The controller reserves child allocations before dispatch. Preparation calls count against the parent ceiling; orchestration is not a provider call.

Every child retains its operation ledger. Parent accounting projects those call identities once and retains unknown calls and unfinished reservations. Stable request identities support restart; changed dependency inputs receive a new execution identity within the original child allocation. The integration package receives reviewed dependency exports and author provenance. Parent completion requires current child reviews and current dependency receipts; it stops at manual acceptance.

## Status and limits

This is an implementation candidate for issue #67. Contract validation and initial synthetic controller tests are under review. CLI/browser composition, autonomous creation of child artifacts, external adoption across a graph, complete crash reconciliation and endpoint certification remain unfinished. Do not treat this document or structural validation as acceptance evidence. No live provider or installed runtime is required for the synthetic tests.
