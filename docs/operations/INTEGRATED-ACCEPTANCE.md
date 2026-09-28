# Integrated operation acceptance

## Candidate

The candidate includes the exact public stack below, then PR #76's source-reference
repair. All base/head relationships were checked against Git objects and current
GitHub PR records on 2026-09-25. Current main is an ancestor. No PR was merged.

| PR | Head revision | Current head checks at inspection |
| --- | --- | --- |
| #50 | 7fca93b51656dcc43083fad06f4ca9a6a27afb75 | Failed |
| #56 | d5b690cf6205e618fad1527af417c947a937245b | Failed |
| #60 | 47005ac269af5adb922b99e669e49da69ce6ee3c | Failed |
| #61 | 69763060dfbdac23797434f7172599116ea643f2 | Failed |
| #63 | 105565ccc71486782bff93976d3987ab6d1b8c76 | Passed |
| #64 | afe619c1c7f116d937a1d0709d60216a9133ae1c | Passed |
| #76 | 60216ef6a14a67d12128d5c8d7bddb909bd6934f | Pending at publication |

Each row after #50 directly targets the preceding PR's branch. The older failed
checks are not relabeled as passing. The integrated candidate contains the
fixture and CI repairs already published in #63/#64.

## Additional acceptance

`tests/test-operation-integrated-acceptance.py` adds independent regression coverage:

- Classification exhaustion persists across controller restarts. External adoption
  proceeds through Verify/Review without Implement, retained drafts/failures or
  usage being reset. Replay dispatches no additional worker.
- A two-file patch interrupted after its first parent write resumes the remaining
  integration from its checkpoint without another worker or accounting charge.
- Tampered Review evidence invalidates Review and Accept while preserving current
  Groom, Implement and Verify evidence.

Three tests passed in 18.457 seconds. An independent agent authored and ran these
regressions after auditing the existing contract and tests. This partial patch
integration test is not package-graph integration certification under #67.

`tests/test-operation-installation.py` makes a fresh disposable clone of committed
HEAD, runs the actual installer into isolated targets, audits the installation,
and exercises its launcher and dashboard HTTP API with synthetic providers. The
source clone revision is checked against the caller's HEAD; uncommitted runtime
changes are intentionally not certified. The operator installation is untouched.

At `60216ef6a14a67d12128d5c8d7bddb909bd6934f`, temporary installation reached
`pending_manual_acceptance`. Four synthetic calls used argv request sizes of
3,073, 6,198, 3,340 and 6,673 bytes (packet sizes 650, 734, 917 and 1,209 bytes).
Replay reused seven operation results and dispatched no worker. Measured worker
execution was 1.629 seconds; observed grant wall time was 7.200 seconds. No
unfinished execution reservation remained. Provider token usage and billing are
unreported by these synthetic executables; they are not inferred as zero.

The actual Chromium fixture on the same runtime passed eleven checks with four
synthetic calls: admission parity, factory composition, pending manual acceptance,
duplicate replay, explicit acceptance, drift, external adoption, failed Verify,
blocked Review, reload and desktop/mobile rendering. The temporary-installation
fixture checks HTTP parity; actual browser clicks are covered separately by
`tests/test-operation-browser.py`.

## Certification boundaries

| Endpoint/profile | Evidence | Status |
| --- | --- | --- |
| Shared operations through independent Review | Synthetic source and temporary-installation fixtures | Candidate acceptance |
| Manual acceptance and branch push | Existing explicit acceptance/local Git fixtures | Synthetic only |
| PR creation and integration CI | #73 | Not certified |
| Package graph | #67 | Not certified |
| Live subscription model run | #2 | Not authorized or executed |
| Installed activation | Separate operator proposal | Not authorized or executed |
| Deployment | #74 optional profile | Not applicable to local/PR-only release |
| Shared-service identity | #75 optional profile | Not applicable to local profile |

Keep #62 open for reviewed stack integration; passing candidate tests do not merge
its prerequisites. Keep #2 open for its mandatory live acceptance. Existing live
rollout proposals remain unexecuted. No private configuration or ticket evidence
is included.

## Sources

- `docs/operations/CONTRACT.md` and `docs/operations/VALIDATION.md`.
- `tests/test-operations.py` and `tests/test-operation-review-regressions.py`.
- `tests/test-operation-integrated-acceptance.py`.
- `tests/test-operation-installation.py` and `tests/test-operation-browser.py`.
