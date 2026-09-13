# Workshop verification — 2026-09-13

The live macOS pilot completed the classroom workflow. This is not production
behavior-proof certification, a Windows run, or a sponsored API billing test.

| Measurement | Earlier full factory run | Completed classroom pilot |
| --- | --- | --- |
| Active duration | 48m 6.375s | 198.3s (3m 18s) |
| Runtime turns / controlled calls | 221 outer turns | 17 bounded calls |
| Fresh input tokens | 426 | 2,194 |
| Cache-write input | 367,244 | 27,196 |
| Cache-read input | 51,376,102 | 0 |
| Output (including thinking where reported) | 153,554 | 14,403 |
| Main usage total | 51,897,326 | 43,793 |
| CLI reported dollar estimate | $13.2819784 | $0.257202 |
| Outcome | Implementation committed; production behavior proof blocked | 8 public cases passed; separate review passed; zero repairs |

Both runs used Claude subscription access. Dollar figures are CLI list-price
estimates, not invoices. Earlier total_cost_usd includes a small Haiku auxiliary
charge; its main usage total above excludes that auxiliary model and any separately
launched reviewer CLI not included in the parent receipt. The classroom calls used
`claude-sonnet-5`, with tools disabled and no child agent loop.

These workloads have different assurance levels. The classroom result uses public
single-turn cases and fresh same-provider review sessions, not hidden heldouts or
cross-provider production review. Do not interpret the reduction as equal proof
for less money. Spec approval in this pilot was performed by the implementing
assistant under the user's authorization, not by a student in a usability study.

## All development trials

| Trial | Status | Calls | Active seconds | Reported/reserved USD |
| --- | --- | ---: | ---: | ---: |
| 1: `workshop-014c777fd4684e19` | failed | 3 | 12.2 | 0.009510 |
| 2: `workshop-c6aba994dff8775d` | failed | 3 | 16.5 | 0.015962 |
| 3: `workshop-e74d9771481a74ff` | failed | 4 | 15.7 | 0.021950 |
| 4: `workshop-10bb68e9c9c533a6` | failed | 5 | 32.4 | 0.044580 |
| 5: `workshop-dcfe74af8bf65cdf` | failed | 4 | 23.4 | 0.024390 |
| 6: `workshop-6d05d7283191e942` | failed | 7 | 76.3 | 0.099276 |
| 7: `workshop-0ec5905a28a79f93` | failed | 16 | 206.5 | 0.458036 |
| 8: `workshop-639c6dc2ee6719a1` | complete | 17 | 198.3 | 0.257202 |

Total: 59 calls, 581.2 active seconds, 121,612 captured tokens, and $0.930906 reported/reserved cost.
The manually stopped contaminated trial has a missing last-call receipt; its
$0.25 reservation remains charged and its unknown token usage is not counted as
zero. These development totals include all retained attempts, not just the winner.

Live findings corrected: JSON fence normalization, explicit requirement-count
limits, stage-specific review instructions, host-enforced case coverage slots,
explicit prompt line arrays, and safe-mode removal of personal instruction context.
The unsafe-context trial was stopped after an unrelated email instruction appeared
in its artifact. It is retained as failed evidence. The final artifact has no such
instruction; `--safe-mode` is now mandatory in both API and subscription calls.

## Verification and evidence

- Offline workshop contracts: 8 passing tests (budgets, resume, drift, one repair, timeout, missing receipt, API isolation, factory dispatch and dashboard visibility).
- Runtime resolver: 3 passing tests (mise shim dispatch, ordinary symlink, missing executable).
- Init: 7 passing tests, including upgrade from old routing without losing roles.
- Output: 9 passing tests; setup: 3; release inputs: 9; dashboard: 9.
- Factory CLI, auth, and preflight shell suites pass. API forwarding and opt-in publication are asserted.
- Existing behavior-proof suite: 25 passing tests in the publication tree and 25 in the active runtime.
- ShellCheck and `git diff --check` pass.
- Installed CLI repeated the completed pilot without additional model calls.
- Installer repair completed. The branding source audit has no findings; full installed audit remains incomplete for three preserved, customized configuration files with unknown ownership. Their old external symlinks were archived and their exact data retained locally.
- A mise installation with no active Codex version now fails resolution before launching the shim; the earlier detached Codex hang is not claimed fixed end-to-end.

Private original receipts: `~/.nightshift/logs/run-3zg04w7r/stdout.log` for the
earlier run; the pilot retains every `RUN.json`, call receipt, and evaluation in
its registered worktrees. A portable committed export is available locally at
`/Users/doctorew/shuttlebay/_ATL_/GSU/Hack-Her-Thon-workshop-verified-20260913`.
That export includes `docs/development-trials.json` and the completed prompt, spec,
cases, grades, and raw model receipts. It is an evidence export, not a moved
resumable worktree. API-key live validation and Windows student-laptop validation
remain necessary before promising classroom readiness on both platforms.
