# Evidence-bound decisions and acceptance

## Clarification

The shared operation controller exposes `question` and `answer` actions. Each
question names an operation, exact assessed binding, question, reason and up to
three options. Each option has an identifier, label and consequence description.
The existing console decision store retains the question and answer with
`continuation_operation` set to `none`. Saving an answer neither grants allowance
nor dispatches a worker.

The question basis includes operation dependencies and relevant source state,
excluding its own answer and repair history. Changed evidence makes the retained
question stale. Current unanswered questions block the operation and dependent
results. Answered questions enter operation dependencies and bounded worker
packets; the exact answer projection is retained in normal and recovered results.
Controlled output changes do not erase the testimony used to produce them.

Workers may return an optional `results.question` only with an abstention and no
patch. The controller persists the question and stops the operation. A subsequent
answer requires reassessment and explicit authorization before execution. Different
questions remain separate; duplicate questions and answers reuse retained records.
Question history is bounded at 100 records and each submitted question is bounded
at 6,000 serialized bytes. Oversized worker context is rejected without truncation.

## Manual acceptance

The `accept` assessment exposes `manual_cases`. For each current manual case,
submit exactly `id`, `case_sha256`, `passed`, `observation` and `evidence` in the
attestation's `cases` array, alongside the assessed `binding`. The case hash covers
the complete scenario row. Every required manual case must appear exactly once,
with literal Boolean `passed: true`, a nonempty observation and an evidence note.
Each text field is limited to 2,048 UTF-8 bytes; the complete attestation is limited
to 12,000 bytes. Evidence notes are operator testimony, not fetched or independently
verified remote artifacts.

The controller validates before retaining authority and again before execution.
Acceptance is a separate operation; it cannot be appended to an automatic recipe.
The result and crash checkpoint retain normalized cases, operator and exact
binding. Duplicate request identifiers cannot replace testimony. When no manual
cases exist, the existing `accepted: true` attestation remains supported.

The browser collects per-case observations and resets confirmations after a new
assessment. Changed source, tests, scenarios, reviewer evidence or policy cannot
reuse stale acceptance. Acceptance consumes no provider call and does not imply
publication, merge or deployment.

## Recovery guidance

The operation panel displays concrete next actions for required decisions,
missing preceding results and repair exhaustion. Exhaustion preserves the original
attempts and allowances. External implementation enters through `adopt`, with the
actual author identity/provider, followed by fresh verification and review.
Cancellation and unknown-execution reconciliation remain the scope of issue #71;
this change does not advertise blind resume or remote exactly-once execution.

## Validation boundary

All fixtures use disposable repositories and synthetic providers. Live provider
accuracy, authentication, token usage, cache billing and endpoint certification
remain unverified. The installed runtime is not changed. Issues remain open until
integration and their complete acceptance criteria are satisfied.

## Candidate receipt

Runtime `9543c332c0e3805e4542e54ec360540c567d35eb` passes the actual Chromium
153.0.8010.12 journey. It includes persisted clarification, per-case acceptance,
duplicate replay, source drift, failed verification, bounded review exhaustion and
external adoption without another implementation. Thirteen synthetic worker calls
were made across two disposable tickets. The exhaustion ticket used eight calls
(three implementation, three review and two preparation calls); external adoption
then used one review call. Its two grants report zero unknown invocations and
9,454 packet bytes. All individual argv and packet sizes are recorded in
`MANUAL-ACCEPTANCE-VALIDATION.json`; the usage block is explicitly scoped to the
exhaustion ticket. Tokens, billing and provider cache usage remain unknown.

The operation suite passed 118 tests before the final dispatcher correction. Six
CLI/API tests pass after that correction, including actual-launcher review failure
and bounded exhaustion. Independent review supplied 11 manual-acceptance and 13
question regressions. A valid bound worker FAIL contract now remains a substantive
operation failure even when the launcher exits one; an unbound transport failure
remains ineligible for automatic semantic repair.

Default-branch integration and live certification remain pending. Safe cancellation
and explicit unknown-effect reconciliation are still being implemented under #71.
