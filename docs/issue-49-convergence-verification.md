# Spec convergence: issue 49

Tracking: https://github.com/doctor-ew/nightshift-community/issues/49

## Implemented behavior

Existing drafts continue to missing validation and review. The prior product
instructions incorrectly allowed draft reuse to jump directly to an approved
tracker. A writer dispatch against an existing draft now requires a current
`spec-repair.json` with a SHA-256 binding and concrete, stable findings. The
controller prepares that brief from retained findings; no regeneration question
is required. Brief validation occurs before provider authentication or execution.
This bounds the requested repair scope; it is not a post-write diff firewall.

The bounded source dispatcher can reuse an already evaluated positive report
without a provider launch or another retry reservation. Reuse binds the request,
Git HEAD, current nonignored workspace files (including dirty/untracked files),
routing, provider policy, author/role options and evaluator assets. The retained
report must match its stored hash. Source changes during review disable reuse.
The canonical evidence and claim-mapping gate still evaluates the returned report.
Negative searches, incomplete dependencies, symlinks/submodules, non-Git requests,
and workspace snapshots above the size/count bounds do not receive cache reuse.
Ignored files are not valid dependencies for reusable positive reports.

Unchanged failed requests are rejected before another provider call, including
requests without registered repair manifests. Repeated explicit CONFLICT claims
are compared by normalized claim text and file, recorded in a portal-readable
receipt, and set the next action to change repair strategy. A later evaluated
report covering those exact claims clears that warning and retains its history.
Paraphrased equivalent findings are not detected. Switching repair authors is
still an orchestration instruction, not enforced provider switching.

Claude fact extraction now uses an isolated system prompt and Read/Glob/Grep tools.
It omits general user/project customizations and the duplicate role prompt in the
user message. Managed CLI policies still apply. Work-specific requirements and
constraints must be supplied in the review request. Other authoring roles retain
their existing execution profiles and configured model routing.

## Measured live result

See `issue-49-live-convergence.json` for the structured receipt. Both samples used
Claude subscription Haiku on a synthetic public source fixture. Each observed a
wrong literal, verified its targeted correction, and reused the accepted report
without a third provider launch.

| Measurement | Baseline | Isolated reader |
| --- | ---: | ---: |
| Instrumented provider launches | 2 | 2 |
| Targeted repairs | 1 | 1 |
| Transport retries | 0 | 0 |
| Provider-active seconds | 19.656 | 11.299 |
| Known tokens, including cache usage | 83,763 | 26,499 |
| Fresh input tokens | 36 | 36 |
| Cache-read input tokens | 57,741 | 18,525 |
| Cache-write input tokens | 23,923 | 6,719 |
| Output tokens | 2,063 | 1,219 |
| Provider estimate, USD | 0.0639711 | 0.0214215 |

Baseline driver elapsed time was 23.384 seconds. The isolated driver's active
segments totaled 12.867 seconds, but reservation-to-finish wall time was 98.382
seconds because the driver paused after misclassifying an expected role FAIL as a
harness error. Its one remaining authorized call completed the repair; its
allowance was not expanded. Each sample allowed at most two launches, 120 aggregate
active seconds, and 180 wall seconds. Total live expenditure was four launches and
110,262 reported tokens. Actual billing, subscription quota consumption, provider
internal call counts and assistant-session accounting remain unknown.

The observed token reduction is about 68% for this one small fixture. Cache state,
model nondeterminism and the tiny task prevent a general performance guarantee.
This is live source-review convergence, not a complete ten-minute specification or
work-ticket delivery. No Jev or RTK savings are claimed.

## Regression verification

Five review reuse/recurrence tests, two repair-dispatch tests, two writer-brief tests,
the retry-budget suite and 130 dispatcher assertions passed. The writer-brief
integration verifies that a redundant writer request makes no provider/auth call.
No consumer work was resumed, no historical budget was reset, and no gate approval
was manufactured. Implementation and these verification records are local; the
GitHub issue is published. Broader end-to-end acceptance remains open on issue 49.

MEX context used: `.mex/AGENTS.md`, `.mex/ROUTER.md`, and
`.mex/context/architecture.md`. The code graph was unavailable; source lookup was
used. The router update is a local working-tree record until published.
