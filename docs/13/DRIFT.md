# Issue 13 specification and implementation drift

Base: integration/nightshift at 44ad7cc4d6af7a30cde2b139d9ad25c19b41c2bf.

All 28 declared paths appear in the implementation diff. There are no unspecified production or test paths. Additional task-local documents are retained review, recovery and validation evidence, as permitted by the specification. No production scope expansion is present.

| Acceptance criterion | Coverage |
| --- | --- |
| AC-1 | Strict scenario validation and task-bound dispatcher admission; missing proof reaches no provider. Independent schema/admission cases pass. |
| AC-2 | Independent classification and authoritative typed public challenge. Wrong digest/incomplete coverage regressions pass; actual runtime challenge passed. |
| AC-3 | Observed deterministic RED and completion-based prototype proof, including strict boolean/integer distinction. Focused cases and real development/final execution pass. |
| AC-4 | Sealed source/scope snapshots, prompt-only pre-admission changes and stale evidence rejection. Scoped implementation remains allowed after admission. |
| AC-5 | Canonical common-Git ledger, durable bounded reservations, retained failures and concurrency regression. Actual resumes preserve prior attempts and counters. |
| AC-6 | Private commitments and explicit exposure invalidate final freshness. Held-out final behavior passed through the repaired installed engine. |
| AC-7 | Verified subscription/no-tool runtime, bounded output/time/process cleanup, no billing fallback. Offline failure-path cases and actual CLI execution are retained. |
| AC-8 | Validated finite configuration, canonical stage/dispatch gates and optional metrics integration. Existing metrics regressions and legacy proof without metrics pass. |
| AC-9 | Recovery sequence and original chronology violation are explicitly retained. Bootstrap and completed-engine real evidence remain separate; copy/symlink installation and regression evidence are recorded. |

Source/copy real acceptance binds the earlier helper revision. Final symlink acceptance binds engine SHA256 3cdd53a30b5dab496a672d07aa9d3c9222bef81a2f00c5ac471842159ac00299 after the routing-asset fix. This qualification is material: the earlier receipts are not represented as current gates for a changed engine.

Blocking drift findings: 0. Unspecified-change warnings: 0. Drift verdict: APPROVE. Independent review and hosted CI are separate delivery gates.
