# Guided operation intake

## Flow

The browser's Guided intake panel and `nightshift intake` use
`scripts/nightshift-intake.py` through the shared operation API. A fresh task can
obtain local CSRF/bootstrap state before an operation plan exists. The initial
source profile supports project Markdown and GitHub issues, using the existing
source normalizers. Other source profiles return an explicit unsupported result.

Preview resolves a source snapshot, records unresolved choices, and displays exact
proposed files and the operation plan. Scope, required behavior, an existing test
script, rules, architecture context and bounded allowances are explicit operator
choices. Missing choices do not produce a placeholder admitted plan. Complete
choices are limited to 4,000 serialized characters, including the persisted answer;
oversized input is rejected without truncation.

Preparation creates request/specification/scenario/plan/source-snapshot artifacts
under the task's documentation directory. It preserves settings and existing
operator files. Source, runtime and input hashes must match the preview. Preparation
never grants allowance or starts a provider. The existing operation panel then
assesses the prepared task and offers separately authorized operations.

## Readiness and identity

The serving revision and controller hashes are distinct from installed runtime
identity. The installed revision is explicitly unverified. Tool presence uses the
capability script's nonexecuting `--presence` mode. It does not probe provider
accounts or models. Authentication/model access remain unverified until an explicit
connection check; their availability is never inferred from an executable path.

Admission reuses the existing baseline, source, manifest and branch predicates.
Missing configuration is visible and can block execution without preventing a
reviewable draft. This slice does not claim complete connection certification under
issue #46. The selected endpoint is local reviewed work; no remote target, PR,
merge or deployment is inferred.

## Decisions, cancellation and recovery

Unresolved choices use retained console decision records with the explicit `none`
continuation mode. Saving intake answers never queues a continuation worker.
Answers remain tied to the source snapshot and the preview. A changed source must
be previewed again. Prepared artifacts do not assert product or manual acceptance.

Cancellation retains the preview, source and existing files. A prepared draft has
no owned execution to cancel and refuses a contradictory cancelled receipt.
Identical or distinct duplicate preparation requests reuse the retained current
receipt. Source or generated-file drift blocks reuse. A crash after a complete file
write can finish the retained creation intent without another provider call. A
partial-byte write requires explicit reconciliation; it is preserved and never
overwritten as if it were a completed write.

## Verification boundary

Synthetic controller tests cover local intake, durable questions, cancellation,
duplicates, stale source and operator files, and CLI/API parity. Independent cases
cover completed-file crash recovery, source/test/generated evidence drift,
protected paths, fresh-project HTTP bootstrap, CSRF, worker-role and symlink
rejection. Actual Chromium tests prepare a fresh local-file request and a synthetic
GitHub issue without terminal intervention, then run the existing operations through
synthetic executable providers. They retain desktop/mobile interaction evidence.
No real provider, installed-runtime change, live ticket or deployment is involved.
