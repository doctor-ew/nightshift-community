# Accepted architecture: operation and verification

## Delivery status

Issue #58 has an initial implementation in draft PR #56. It is not installed in the active runtime. The full PR's previously reported CI failures and live consumer acceptance remain open. No Jira ticket or paid model run was started for this implementation.

## Authority and persistence

`scripts/nightshift-architecture.py` registers an explicit operator-accepted snapshot of a decision associated with an upstream HTTPS reference. The upstream ticket remains the source of truth; the operator must explicitly register an updated decision when its authority changes. Automatic upstream synchronization is not implemented.

The local decision snapshot is stored beside existing controller state in the common Git directory, shared by ticket worktrees. Records retain hashes, operator provenance, scoped constraints, and a bounded copy of the accepted reference source. Supersession requires the active prior record hash and a reason. Earlier records are retained. This local state is not automatically transported to another clone or Azure; provision it explicitly before such a run.

Workers receive the resolved record and pinned source. MEX supplies additional bounded graph source; unavailable or stale graph results do not remove the accepted reference. Historical source and Markdown cannot supersede the record. The controller rejects a changed decision set during dispatch. This is workflow enforcement, not OS isolation from a malicious process with unrestricted Git-directory access.

## Operator interface

Run from the candidate Nightshift checkout. The following paths are placeholders for an existing consumer checkout and a reviewed proposal file:

```sh
python3 scripts/nightshift-architecture.py accept --project /path/to/consumer --input /path/to/approved-decision.json
python3 scripts/nightshift-architecture.py show --project /path/to/consumer
python3 scripts/nightshift-architecture.py check --project /path/to/consumer --task TICKET
```

The proposal requires `id`, `decision`, `operator`, `upstream`, `scope`, `reference`, and `constraints`. `reference` is a repository-relative text file, limited to 8 KB; its accepted content is captured during registration. `scope` is a list of repository-relative, case-sensitive shell-style patterns. The checker uses Python `fnmatch`; slashes are not special, so `pages/*` also matches nested paths. Constraints are objects with `kind` and `value`. Supported kinds are `forbidden_path` and `forbidden_literal`. A literal rule matches exact bytes, including comments and strings; it is not an import parser or a semantic abstraction detector. Use a narrowly chosen scope and rule.

For replacement, retain the decision `id` and provide `supersedes` with the active record's `sha256`, plus `reason`. Automatic repair never calls the acceptance interface. All current project records are delivered conservatively to each ticket; per-ticket decision applicability filtering is not implemented.

## Beads linkage

When an existing local Beads ledger is present, the controller invokes `scripts/nightshift-beads-mirror.sh` to mirror decision references and link them from a dedicated architecture-links bead for the ticket, preserving the original ticket bead's description. A linked worktree can use the main checkout's ledger. Beads receives identifiers, upstream references, and decision hashes, not a competing copy of policy text. Link results are cached in ticket state. Missing or failed linkage is visible as unavailable and does not disable constraints. A failure is not retried on every stage; the initial result remains evidence of that attempt.

## Independent checks and UI

After implementation, review, drift, and QA workers return, the controller runs path/literal checks over tracked and nonignored untracked files in the scoped paths. A worker PASS cannot override these findings. The controller retains check implementation, decision, and source hashes with the ticket identity. A source correction permits another bounded attempt; an unchanged failed attempt cannot launch repeatedly. Budget history is retained.

The existing ticket UI shows accepted decisions, their scopes and reference paths, check results and findings, and Beads availability. Stale controller evidence is labelled for revalidation. Manual acceptance remains separate.

These checks do not prove arbitrary worker-declared test commands executed; the existing final behavior evidence gate remains required. Semantic equivalents, renamed factories, intentional exceptions, and architecture-specific AST rules still require the broader held-out evaluation and review described in `docs/architecture-decision-enforcement.md`.

## Reproducible offline test

```sh
bash tests/test-architecture.sh
```

This suite exercises explicit supersession, tamper detection, cross-worktree sharing, exact reference retention without MEX, scoped violations, unsafe symlinks, the actual Beads mirror shell script against a deterministic CLI fixture, and the next-ticket controller failure/resume sequence. The later ticket retains conflicting historical Markdown, returns a misleading PASS after introducing a prohibited literal, and is blocked by the independently executed check. A correction resumes to pending manual acceptance without changing the existing budget or repeating completed review on a further resume.

The Beads transport is stubbed in these tests, and the architecture regression is synthetic. They are not live Beads-service, semantic-model, or Jira-delivery proof. The same wrapper also runs existing handoff and controller regressions and is discovered by the offline CI harness.

## Verification receipt

Local verification on 2026-09-24: five architecture tests, two handoff tests, five controller tests, eleven dashboard model tests, and the dashboard production build passed. The real-shell controller test required execution outside the restricted sandbox because `/dev/fd` process substitution was denied; provider processes in that test are synthetic. The final architecture rerun also covered a failed existing-Beads update and missing routing before dispatch.

This does not clear the previously reported eight full-suite CI failures or establish live Jira delivery. The active installed runtime was preserved.

## MEX preparation during init

`nightshift init` now prepares MEX by default. It reuses an available CLI; if missing, it installs the pinned `mex-agent@0.8.2` package privately under the Nightshift home, without a global npm install. The handoff adapter resolves that private installation too. The package name and version are taken from the inspected MEX 0.8.2 distribution documentation.

Init runs `mex graph status --json`: fresh graphs are reused, stale compatible graphs are refreshed, and a missing graph is built only when no graph database exists. Corrupt, degraded, or otherwise unsafe existing graphs are preserved for explicit maintenance. This does not run `mex sync`, which prepares model-facing scaffold repairs.

Installation and graph preparation share a default 60-second allowance. `--mex-timeout` accepts 1–600 seconds; `--mex off` explicitly skips preparation. Timeout or dependency failure produces an unavailable result with elapsed time and reason, without consuming a model budget. Nightshift project initialization remains usable with the pinned-reference fallback. Newly generated MEX ignore rules are committed separately; graph databases remain derived local files. Existing memory and unrelated files are not staged.

A live one-source-file smoke test with the already installed CLI built its graph in 0.754 seconds and reused it in 0.206 seconds. These timings exclude package download and do not predict large-repository latency. Four additional offline tests cover fresh reuse, refresh/build selection, private installation, unsafe graph preservation, timeout reporting, and default/repeated init. The existing initialization tests explicitly skip MEX so they remain offline.

A second live smoke test exercised `nightshift init` itself in a fresh disposable repository with the installed MEX CLI: graph preparation took 0.746 seconds, repeated init reused it in 0.209 seconds, and the repository remained clean. No model was started. First-time package download remains covered by a deterministic installer test rather than a live download measurement.
