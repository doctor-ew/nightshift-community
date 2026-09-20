---
title: 'Default-on Nightshift efficiency adapters'
type: 'feature'
created: '2026-09-20'
status: 'done'
route: 'full'
review_loop_iteration: 1
baseline_commit: 'e2484e7014aca483185d37234409c552fc134c77'
context: []
---

<frozen-after-approval reason="User authorized A-Z implementation on current branch">

## Intent

Implement the core of the revised [epic](../../docs/FOUNDRY-JEV-EPIC.md): RTK capture/filter execution and Jev shadow evaluation within existing Nightshift runtimes. Azure is out of scope. Both features are default-on when available/configured with explicit opt-outs. Deliver working entrypoints, runtime integration, private receipts, documentation, and offline verification. Empirical live savings and experimental tool/browser routing remain separately measured follow-ups, never fabricated as completed.

## Boundaries & Constraints

Always preserve command exit codes, independent review gates, provider/auth choice, and raw command evidence. Execute commands once. Keep endpoint, model, credentials reference, enablement and limits configurable. Prefer Python standard library and existing capability infrastructure. Preserve unrelated untracked user files and concurrent edits; you are not alone in the repository. Do not edit AGENTS.md, CLAUDE.md, existing epic, or generated BMad infrastructure.

Never install global hooks, transmit whole repositories, reveal keys or payloads in receipts/errors, reinterpret shell strings, treat confidence as authorization, run paid calls, or add a Foundry adapter. Do not change role prompt model selection. No push/deploy. Record actual observed results only.

## I/O & Edge-Case Matrix

| Scenario | Input/state | Expected behavior | Error handling |
|---|---|---|---|
| Eligible command | Default enablement, RTK available | Run original argv once, save raw streams, filter captured stdout with RTK, preserve stderr/code | Private receipt |
| Bypass | Opt-out, exact source/diff, machine output, unsupported command | Raw output, original execution/code | Reason in receipt |
| RTK absent/broken | Missing binary, timeout, invalid filter result | Return already-captured raw output | Never rerun command |
| Jev configured | Explicit evidence input and key | One bounded shadow evaluation, typed results and provenance | No gate authority |
| Jev absent/disabled | No key/input, or opt-out | Skipped receipt, no network | Continue ordinary pipeline |
| Jev failure | HTTP/schema/timeout/oversize | Unavailable receipt, no payload leakage | No false PASS/FAIL |
| Invalid configuration | Wrong types/limits/endpoint | Clear fixed error reason | No unintended execution/network |

</frozen-after-approval>

## Code Map

- scripts/nightshift-factory.sh: command dispatch near lines 25–51, help near 78, provider prompt near 532, final run status near 702–717. Add efficiency subcommands before update/output wrappers, keeping recursive-factory guard intact. Workers can call the helper directly.
- scripts/nightshift-agent.sh: EXECUTION_CONTEXT near 275–293 is provider-neutral runtime guidance insertion point; do not alter provider cases or schema/review contract.
- scripts/nightshift-capability.sh: optional tool probe/cache and --has/--which; extend RTK capability with stale-cache handling.
- docs/NIGHTSHIFT-COST-POLICY.md and docs/RUN-MEASUREMENTS.md: preserve billed/estimated/unknown distinctions, not competing dollar calculations.
- tests/test-factory-cli.sh, tests/test-agent-dispatch.sh, tests/test-adapter-thinness.sh: affected regression suites; inspect before changing interfaces.

## Tasks & Acceptance

Execution:
- [x] scripts/nightshift-efficiency.py and efficiency.json: configuration/CLI/private receipts, RTK exec and Jev evaluate; split helpers only when warranted.
- [x] scripts/nightshift-factory.sh and scripts/nightshift-agent.sh: route `nightshift exec` and `nightshift evaluate`, advertise bounded helper usage; optional end-of-run evaluation using explicit NIGHTSHIFT_JEV_INPUT and preserving provider status. Missing explicit input must never trigger repository discovery/upload.
- [x] scripts/nightshift-capability.sh: optional RTK resolution.
- [x] tests/test-efficiency.py: offline coverage of every matrix row and launcher routing.
- [x] docs/EFFICIENCY-ADAPTERS.md and README.md: user-visible installation/configuration/opt-out/limits and runnable examples; cite code file:line for snippets.

Acceptance criteria:
- Given a configured project, when helper/factory runs, then config precedence is per-invocation option, environment, project .nightshift-efficiency.json, shipped efficiency.json; keys are only environment references, not secret values in config.
- Given an eligible noisy test/build/log command, when execution finishes, then full raw stdout/stderr and hashes are retained in unique mode-0700 directories with mode-0600 files, compressed stdout is separate, exit status is unchanged, and bytes/latency are measured without fake billed savings.
- Given filtering failure, when output is returned, then original command has executed exactly once and raw bytes are returned unchanged. Exact source reads, diffs, JSON/NUL/machine flags bypass compression. Start with a conservative tested command-family allowlist; document it.
- Given explicit evaluation evidence, when Jev is configured, then typed judgments are validated and recorded with input/rubric hashes, selected/reported model, available nonnegative usage and unknown cost; failure details cannot leak key/request/response contents.
- Given configured evaluation without explicit approved input, when a normal run ends, then a visible skipped receipt explains no evidence input; existing gates and exit status remain intact. Opt-outs prevent calls.
- Given an unavailable optional component, when normal engineering work runs, then the component's status is visible and never changes PASS/FAIL authority.

## Design Notes

RTK should filter already-captured output using `rtk pipe --filter <verified-filter>` (upstream src/main.rs:737 and src/cmds/system/pipe_cmd.rs:resolve_filter), not wrap execution and hope raw logs survive. Use command-matched filters for a conservative allowlist. Generic `rtk log` can discard test lines without severity keywords and must not summarize arbitrary test output. Filter only stdout; preserve stderr separately. Never interpolate argv into a shell. Avoid unbounded memory, process lifetime, disk writes, redirects, or credential forwarding to changed origins. Filesystem receipts must avoid symlink redirection and collision overwrites.

Verified API contract: https://docs.typesafe.ai/introduction/quickstart.md documents POST https://api.typesafe.ai/v1/systemone, Bearer auth, JSON state/model/questions. Noul questions use type=noul and instructions; response has model, answers[name]={type:noul,noul:number in [0,1]}, usage input_tokens/output_tokens. Use focused versioned built-in Noul criteria; no SDK dependency needed. Do not invent confidence for Noul. HTTPS endpoints only, with explicit loopback allowance for offline mock server tests. Do not follow redirects with credentials. Bound body size and total deadline, sanitize errors, and avoid logging server bodies. Rubric should evaluate the explicit evidence, not claim engineering completion.

## Implementation Notes

User approved proceeding across both components and on current branch; no further planning approval requested. Implementation owner may adapt internal boundaries to verified code, preserving stated behavior. Root is updating the epic and will independently inspect sources/review; avoid overwriting unrelated edits.

## Spec Change Log

- Review pass 1: clarify non-frozen integration details: validate only active adapter values (structurally invalid configuration still fails); record safe implementation/config/endpoint fingerprints; place Jev observation before metrics finalization; wire Python tests into the shell CI entrypoint. KEEP capture-once, raw failure output, explicit evidence-only network requests, private receipts, default-on opt-outs, and existing gates. User's A-Z authorization covers these in-scope repairs; retain existing working code while repairing demonstrated defects.

## Review Triage Log

Pass 1: 5 high, 10 medium, 0 low/false/maybe-false. Duplicate findings retain individual rows and share repairs. All findings are in-scope implementation/verification repairs.

| Finding | Verdict | Evidence and action |
|---|---|---|
| Blind 1: cross-adapter configuration coupling | medium | config validates every section before exec/evaluate; isolate active values and test. |
| Blind 2: SIGTERM orphan | high | capture starts a new session but only catches KeyboardInterrupt; add termination/reaping regression. |
| Blind 3: limit-crossing data loss | medium | chunk is discarded before target.write; retain permitted prefix and partial flag. |
| Blind 4: capture I/O hang | high | exception leaves reason unset then proc.wait blocks; terminate on capture error. |
| Blind 5: closed output pipe loses receipt | high | forwarding precedes receipt.save; persist first and test delivery failure. |
| Blind 6: exact listing modes filtered | medium | allowlist accepts collect/list modes; explicit bypass and raw assertions. |
| Blind 7: evaluation outside accounting | medium | no evaluation run ID, call after summary; correlate and record before summary. |
| Blind 8: missing reproducibility provenance | medium | no implementation/config/endpoint hash; add safe hashes. |
| Blind 9: incomplete real-filter verification | medium | fake RTK exercises only pytest; add command-family fixtures and pinned binary smoke. |
| Edge 1: capture I/O hang | high | Same demonstrated cleanup path as Blind 4; shared repair. |
| Edge 2: SIGTERM orphan | high | Same detached child path as Blind 2; shared repair. |
| Edge 3: closed output pipe | medium | Same receipt-ordering issue as Blind 5; shared repair. |
| Edge 4: filtering interruption becomes success | medium | interrupted filter falls back with original zero code; propagate cancellation with separate command outcome. |
| Verification 1: tests absent from CI | medium | shellcheck workflow enumerates test-*.sh; add Python-suite shell wrapper. |
| Verification 2: factory completion untested | medium | direct helper mock does not exercise post-provider evaluation; add factory integration cases. |

### Focused re-review

- Medium, patch: cancellation after partial invalid UTF-8 filter output reached decode before the cancellation check, losing exit 130/143. Move cancellation handling ahead of decode and add regression. Other initial edge cleanup findings were confirmed resolved by the independent reviewer.

## Verification

Run the new offline unittest suite and affected existing shell suites. Verify shell syntax, Python compilation, CLI help, and a real local command smoke test. If RTK is not installed, test fallback honestly and mark real binary verification pending. No live Jev calls or claimed savings without evidence.

## Final resolution

All 15 initial review findings and the focused invalid-UTF-8 cancellation finding were repaired. Independent edge re-review confirmed no remaining blocker from its findings. Final independent execution passed 23 adapter tests, 117 dispatcher assertions, factory CLI/preflight/auth/metrics suites, adapter thinness, release inputs (9 tests), and setup UX (3 tests). Python compilation, changed-shell syntax, and whitespace checks passed. Real pinned RTK filter smoke evidence is retained; no live Jev calls or billed-savings claims were made. See [verification report](../../docs/efficiency/VERIFICATION.md). NJ-07–11 remain separate empirical follow-ups in the epic.
