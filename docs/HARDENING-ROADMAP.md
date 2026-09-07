# Hardening roadmap

Prioritized 2026-09-07. Rankings below are engineering estimates, not measured savings.
Do not modify or restart the active Idea Coach workflow as part of this roadmap.
Ship through isolated branches and integration PRs; retain final independent review,
regression, drift and applicable live evaluation. No paid API fallback. Local models
and MEX remain optional. Do not update the installed runtime during an active run.

## Now / next / later

| Order | Horizon | Ticket | Expected benefit | Relative effort / reason |
| --- | --- | --- | --- | --- |
| 1 | Now | [#15 Scoped verifier authorization](https://github.com/doctor-ew/nightshift-community/issues/15) | Unblocks required independent review | Small/medium; resolve contradictory dispatch policy without weakening recursion controls |
| 2 | Now | [#8 Preflight and measurements](https://github.com/doctor-ew/nightshift-community/issues/8) | Avoid expensive invalid starts; establish baseline | Medium; shared foundation, currently blocked by verifier authorization |
| 3 | Now | [#13 Pre-build behavioral proof](https://github.com/doctor-ew/nightshift-community/issues/13) | Find wrong assumptions before broad implementation | Medium; risk-based thin proof, not another universal LLM stage |
| 4 | Next | [#9 Bounded handoffs](https://github.com/doctor-ew/nightshift-community/issues/9) | Reduce repeated context and preserve decisions | Medium; explicit required-context contract |
| 5 | Next | [#11 Targeted repairs](https://github.com/doctor-ew/nightshift-community/issues/11) | Avoid repeating unaffected work | Medium; retain full final verification and broaden checks on uncertainty |
| 6 | Next | [#10 Evidence cache](https://github.com/doctor-ew/nightshift-community/issues/10) | Reuse verified work | Medium/high; invalidation and provenance must be correct before trusting hits |
| 7 | Later | [#12 Measured gearshifting](https://github.com/doctor-ew/nightshift-community/issues/12) | Match model capability to job | Higher calibration burden; baseline and quality comparison first |
| 8 | Later | [#14 Optional MEX spike](https://github.com/doctor-ew/nightshift-community/issues/14) | Reuse project decisions and handoff context | Time-boxed discovery; no mandatory memory service or local model |

#13 design can proceed alongside #8; its proof gate does not require the metrics
implementation to exist. #9 precedes #11. #10 and #11 are otherwise independent;
their ordering reflects expected effort and stale-evidence risk, not a hard dependency.
#12 needs measured comparisons, not every cache feature. #14 needs the #9 contract;
neither #9 nor #10 depends on MEX. Re-rank using observed bottlenecks.

## Behavioral proof design

Architect: map requirements to observable and forbidden behavior, identify uncertain
assumptions, and propose counterexamples. Independent reviewer challenges both design
and cases. Run a minimal prototype using the intended runtime before implementing
surrounding artifacts. Record prompt/spec hash, inputs, outputs, provenance, pass/fail/
unknown and bounded repair attempts. This still requires a small executable artifact;
architecture reasoning alone cannot prove live model behavior.

Keep held-out final cases separate. Do not feed expected answers to the model under
test, weaken criteria to make a run pass, or treat missing runtime access as success.
For deterministic features, reuse focused contract/RED tests rather than adding an
unnecessary model call. These gates reduce risk; they do not guarantee zero defects.

## Measurement and promotion

Compare equivalent fixtures and runtime settings. Record elapsed time, observed input/
output tokens (unknown is null), repair attempts, intervention and gate pass rates.
Measure early defects and downstream rework, not just cheaper individual calls.
Quality regression blocks default promotion. Small pilots provide evidence, not a
guarantee of equivalent capability. Final regression and independent review remain.

## MEX boundary

[MEX](https://github.com/mex-memory/mex) describes Git-shared project memory,
code-grounded context and structured handoffs. Evaluate these as optional context
inputs, not as current execution proof or an alternate ticket source of truth.
Pin the evaluated revision and verify interfaces. Missing/stale MEX must not break
Nightshift; no automatic memory writes or cross-project private-context ingestion.

## Sources and implementation anchors

- [Issue #8](https://github.com/doctor-ew/nightshift-community/issues/8): baseline scope.
- `scripts/nightshift-factory.sh`: preflight, authentication and recursion guard.
- `scripts/nightshift-agent.sh` and `commands/nightshift-adversarial.md`: dispatch and independent verification policy.
- `scripts/nightshift-claim-cache.sh`: existing claim cache to extend, not duplicate.
- `scripts/nightshift-route.sh`: existing deterministic route selection.
- [MEX upstream README](https://github.com/mex-memory/mex#readme): context/handoff capabilities; no integration has been implemented here.
