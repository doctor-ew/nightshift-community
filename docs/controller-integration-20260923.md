# Controller integration: implementation and acceptance status

## Delivery boundary

The implementation on `nightshift/structural-controller` is under review. It is not the activated installation. The installed repair branch retains the tested console recovery implementation while this broader change is completed. No consumer workflow was restarted, no exhausted allowance was renewed, and no consumer source was published.

## Implemented behavior

`scripts/nightshift-pipeline.py` stores completed stage receipts, exact unresolved findings, recorded operator decisions, attempts, and the next action in one ticket controller record. It resolves author and independent reviewer routes before dispatch. Claude-only uses separate Claude processes. Resume validates input and evidence hashes and continues the missing stage; historical attempts remain charged. Required final behavior proof remains authoritative, including pending manual acceptance.

Workers write receipts in their task documentation directory, which is writable inside their sandbox. The controller validates and copies each receipt into its durable record. Zero exit without a receipt does not pass. Receipt validation requires successful check declarations and matching retained file hashes; the final behavior gate validates canonical execution evidence. Worker declarations alone are not independent proof of every declared command.

`scripts/nightshift-handoff.py` bounds handoffs to 24 KB. Decisions and findings are never silently truncated. Optional MEX retrieval has bounded output and time, includes only graph-backed source, and rejects stale or partial responses. Missing retrieval does not block ordinary source access. Graph text remains untrusted data.

`scripts/nightshift-jev-evaluation.py` evaluates an explicit six-case public synthetic corpus. It records service requests, defect detection, false positives, and unknown billing separately. It does not replace a required review. The local measurement returned `NO_KEY`, zero service requests, and zero avoided Claude calls. Unit tests use synthetic responses; they are not live Jev quality evidence.

## Verification

- `tests/test-pipeline.py`: three passing tests, including real shell dispatch to synthetic Claude executables and real behavior-proof fixtures. The failed review returns zero without a receipt. Resume dispatches only review, drift, and QA; the call count advances from four to seven; the original deadline remains unchanged; a further resume dispatches nothing and retains pending manual acceptance.
- The saved-answer regression rejects missing routing before launching or changing the existing budget. It retains the answer, never creates a second question, and invalidates review evidence when source changes.
- `tests/test-handoff.py`: two passing tests for missing/stale graph results and handoff overflow.
- `tests/test-jev-evaluation.py`: two passing tests for missing credentials and labelled synthetic scoring.
- `tests/test-factory-cli.sh`: passing worker-level CLI regression. It explicitly tests one stage; it does not treat stub process success as controller completion.
- Dashboard model suite: eleven passing tests, including authoritative pending-manual and stale-evidence states; dashboard build passes.

## Outstanding acceptance

Do not close the broader request or advertise production readiness from these fixtures. Remaining work includes legacy stage-evidence import, deterministic publication after verification, batch migration, named-branch parity, readiness wizard delivery under issue 46, and live ten-minute specification delivery under issue 49. Canonical stage documents still contain operator-interaction paths; their compatibility with controller decisions needs full acceptance coverage. Semantic-finding repair requires additional real-dispatch fault tests.

The CxFlow repository graph refused reads with `GRAPH_INDEX_READER_SIDECAR_ACTIVITY` because a WAL recovery boundary was present. Its index, receipts, and source were preserved. No successful CxFlow retrieval or cross-project acceptance is claimed.

The Nightshift graph rebuild indexed 99 files without parse failures. A broad scope request returned partial evidence and was correctly rejected by the adapter; a narrower request returned source-backed output. This is retrieval evidence, not a measured token-saving result.

## Preserved publication inventory

PR 50 carries convergence and console recovery. PRs 51, 52, 53, and 54 preserve unpublished onboarding, ticket 35, ticket 46, and convergence evidence respectively. PR 55 integrates the tested initialization, unattended worker, and installation audit fixes. The preservation PRs are drafts; their artifacts are not implicitly approved or merged.
