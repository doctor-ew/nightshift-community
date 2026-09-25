# Decision recovery validation

All providers in these regressions are synthetic. No ticket, installed runtime,
real allowance or real model was changed by this validation.

| Check | Result | Tests/assertions |
| --- | --- | --- |
| `python3 tests/test-decision-engine.py` | Pass | 20 |
| `python3 tests/test-recovery-decisions.py` | Pass | 9 |
| `python3 tests/test-controller-recovery.py` | Pass | 15 |
| `python3 tests/test-pipeline.py` | Pass | 5 |
| `python3 tests/test-console-continuation.py` | Pass | 7 |
| `python3 tests/test-jev-evaluation.py` | Pass | 2 |
| `python3 tests/test-efficiency.py` | Pass | 23 |
| `python3 dashboard/test_server.py` | Pass | 11 |
| `node --test dashboard/test-model.mjs` | Pass | 14 |
| `bash tests/test-agent-dispatch.sh` | Pass | 130 |

ShellCheck and whitespace checks passed. Both dashboard bundles rebuilt successfully using the repository lockfile's
existing dependencies. Independent code review and a separate run of the 20
engine tests and nine compact integration tests found no remaining blocker in the
compact authority path. Original recovery tests cover concurrent authorization,
restart before adoption, unfinished reservations, changed hashes, unresolved
findings, original-budget preservation and prevention of implementation reentry.

`DECISION-VALIDATION.json` records a separate synthetic measurement: four Jev
requests, two independent scope/oracle reviews and one cached review-stage
judgment. Jev request sizes were 3,766, 7,205, 3,713 and 3,701 bytes. These are
fixture measurements, not a comparison of live model cost or latency. Each
provider request is limited to 24 KiB; unknown/oversized evidence fails closed.

The scope/oracle reviews are intentionally mandatory under the initial policy.
Other decisive judgments use stable sampling; uncertain scores escalate. Credential,
transport and schema failures block without a fallback loop. Changed or missing
raw decision artifacts invalidate cached approval.

The first dispatcher run reported 126 passing and four failing assertions.
Those tests assumed Claude but the branch's default extractor route selected Codex.
The temporary fixture now pins Claude for Claude-specific authentication and tool
assertions. The complete rerun passed 130 assertions; production routing is unchanged.
Additional prerequisite checks passed: console recovery 4, project context 16,
routing 4, provider-policy and factory CLI suites. The initial broader efficiency fixture entered the full controller from an uncommitted temporary repository. It now explicitly exercises the intended synthetic worker efficiency hook, matching the existing companion fixture. All 23 efficiency tests pass; production behavior is unchanged. The dedicated existing Jev regressions also pass.

Live calibration, prepared live evidence mappings, deployment identity and
installed-browser acceptance remain outstanding. The implementation must not be
represented as live ticket completion. See `DECISION-RECOVERY.md` for the ordered
rollout work and authorization boundary.
