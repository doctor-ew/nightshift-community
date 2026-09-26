# Work-package composition

## Contract

`scripts/nightshift-work-packages.py` validates version 1 graphs. Each child references an ordinary operation plan and declares its inputs, owned outputs, interfaces, prerequisites and allowance. The parent declares requirement IDs and aggregate limits. A final integration package depends transitively on every child and covers every parent requirement.

Validation rejects cycles, missing dependencies, overlapping ownership, undeclared cross-package interfaces and insufficient aggregate allocation. Hashes bind referenced plans and input contents. Valid structure is not semantic approval. Templates contain data; they do not carry approvals or allowances.

## Controller candidate

`scripts/nightshift-package-controller.py` composes the existing Groom, Implement, Verify and Review operations in isolated disposable repositories. Preparation uses the ordinary Groom recipe. Its bounded packets include declared child contracts so independent challenge can evaluate semantic coverage. The controller reserves child allocations before dispatch. Preparation calls count against the parent ceiling; orchestration is not a provider call.

Every child retains its operation ledger. Parent accounting projects those call identities once and retains unknown calls and unfinished reservations. Stable request identities support restart; changed dependency inputs receive a new execution identity within the original child allocation. The integration package receives reviewed dependency exports and author provenance. Parent completion requires current child reviews and current dependency receipts; it stops at manual acceptance.

## Status and limits

This is an implementation candidate for issue #67. Contract validation, sequential composition, CLI/browser access, external child adoption and targeted crash recovery have synthetic tests. Autonomous creation of child artifacts, conflict-safe concurrency, complete crash reconciliation and endpoint certification remain unfinished. Accepted architecture records are projected verbatim into child ledgers; changes conservatively invalidate all child authority bindings. Do not treat this document or structural validation as acceptance evidence. No live provider or installed runtime is required for the synthetic tests.

## Synthetic integration evidence

At `17c2a27`, Chromium 153.0.8010.12 exercised decomposition preparation, independent challenge, graph execution, CLI accounting parity and browser resume. The disposable fixture made 14 synthetic executable calls; resume made zero additional calls. The recorded argv request sizes were 9517, 12678, 3153, 6322, 3415, 6788, 3157, 6326, 3422, 6796, 3907, 7076, 4190 and 7570 bytes. Controller packet accounting totaled 29108 bytes. Execution measured 4.653823418004322 seconds, with zero unknown calls and zero remaining reserved seconds. Token usage and billed cost are unknown; these synthetic calls do not establish provider costs or live endpoint behavior.

The shared operation regression suite passed 24 tests at this source state. A separate external-adoption test confirmed that the adopted child receives no additional Implement call, its affected integration package is reimplemented, an unrelated child's ledger remains byte-for-byte unchanged, and replay adds no calls. Parent integration rejects individually passing children when their combined behavior fails the parent requirement. These results do not certify live providers.

## Entry points

Use `scripts/nightshift-factory.sh packages validate --project <directory> --graph <graph-file>` for structural validation. Controller actions are `assess`, `view`, `prepare`, `authorize` and `run`, with `--task` selecting the parent operation plan. Preparation requires an existing Groom authorization; composition requires its own assessed binding and operator authorization. The browser exposes the same controller through `packages-` actions on `/api/operations`.

`view` retains accounting and state when graph assessment fails. A current external child adoption selects Verify and Review only. Imported-input refresh checks all changed destinations before writing and retains an update intent; unexpected operator edits require reconciliation. Completed allocations continue to report later unknown child reservations. Retained standalone calls count against child and parent ceilings even when all results would otherwise be reused.

## Converged prerequisite candidate

The integrated candidate is based on PR #80 at `9d3ba9a23c9f8b0bb36bc7852719cf3d7dd11847` and incorporates PR #82 at `b32e19d461693b9dd3746ef1554a87bb4cf040dd`. Independent comparison with PR #81 at `9dd353bb379d696c60afe938920daa114d00e5a1` identified preparation-plan protection, canonical preparation inputs, preparation identity/publication restrictions and explicit templates to retain. These safeguards are implemented in the existing validator; no second scheduler or divergent validator is introduced.

Version 2 adds named, versioned templates for the existing factory recipe. Preparation validation binds the actual preparation plan, input bytes and exact supplied graph. Eight independent convergence cases pass. At `c86c7a26ce86fc99cf6fc84e9356248b5aa2c125`, twelve independent controller cases passed in 92.207 seconds and six retry-admission cases passed in 26.176 seconds. Actual Chromium/launcher composition again made 14 synthetic calls and zero replay calls; provider execution measured 5.125894040993444 seconds with no unknown usage. Request sizes match the earlier recorded 14-call sequence.

This candidate still has separate preparation and composition wall windows. It does not establish a shared cumulative wall allowance. Autonomous inline-artifact authoring and durable preparation wall receipts are being implemented in a separate follow-up, with independent review and synthetic acceptance before publication. Independent-reviewer tokens and costs are not exposed.

The complete offline harness at the frozen `c86c7a2` candidate passed 49 suites with zero failures. Its retained log is `test-output/roadmap-67/integrated-offline.log` in the isolated integration worktree. The harness changed an adapter executable bit and generated bytecode; these effects are not part of the published source changes. No operator checkout or installed runtime was used as a test target.
