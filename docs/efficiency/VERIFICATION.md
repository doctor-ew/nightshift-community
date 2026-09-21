# Efficiency adapter verification

Date: 2026-09-20. Branch: `chore/jev-epic`. Baseline: `e2484e7014aca483185d37234409c552fc134c77`.

The core [epic](../FOUNDRY-JEV-EPIC.md) tasks NJ-01–06 are implemented and locally verified. RTK and Jev default on when available/configured, with independent opt-outs. Azure is outside scope. See the [operating guide](../EFFICIENCY-ADAPTERS.md).

## Executed checks

| Check | Result |
|---|---|
| `bash tests/test-efficiency.sh` | 23 tests passed; local HTTP mocks, no paid calls |
| `bash tests/test-agent-dispatch.sh` | 117 assertions passed |
| `bash tests/test-factory-cli.sh` | Passed runtime defaults, argv preservation, failure boundaries |
| Factory preflight suite | Passed admission and retained-state invariants |
| Factory authentication suite | All five categories passed |
| Run metrics suite | Passed concurrent accounting, unknowns, exit preservation, privacy |
| Adapter thinness suite | Passed |
| Release inputs suite | 9 tests passed |
| Setup UX suite | 3 tests passed |
| Python compilation, changed-shell syntax, `git diff --check` | Passed |

Three independent review lenses identified configuration coupling, process cleanup/cancellation, output bounds, receipt ordering, exact-output bypass, provenance/accounting, and verification gaps. All 15 initial findings plus one focused cancellation/decode finding were repaired and regression-covered. Focused edge re-review confirmed resolution.

## Real binary evidence

[RTK smoke artifact](rtk-smoke.json) retains synthetic inputs and outputs for the official RTK v0.49.0 macOS arm64 release, verified against its release asset SHA256 before execution. Filter samples cover pytest, cargo-test, vitest, successful empty tsc output, and git status. A separate helper invocation with the real binary preserved a successful git-status command and its raw evidence. These checks validate representative interfaces and fallback behavior; they do not prove semantic equivalence for arbitrary output.

## Remaining work

No live Jev service request, labeled accuracy study, paid-model benchmark, or real accepted-ticket cost comparison was run. Offline Jev coverage verifies the documented API contract, bounded failures, explicit-input behavior, factory integration, and observational accounting. Credentials and explicitly approved evidence are needed for live evaluation.

NJ-07 controlled comparison and NJ-11 adoption evidence remain open. NJ-08 routing, NJ-09 gateway, and NJ-10 browser experiments remain separate, pending that evidence. Compression bytes are not billed-dollar savings. Existing review/test/drift gates retain authority. Workshop's separate runtime and native Windows command capture are not supported by this integration.
