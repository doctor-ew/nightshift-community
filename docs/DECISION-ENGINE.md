# Bounded semantic decision engine

`scripts/nightshift-decision-engine.py` supplies a reusable semantic-decision
boundary. The caller retains authority over operator authorization, deterministic
checks, review independence, allowances and controller transitions. It does not
replace those checks with a model judgment.

## Admission contract

Each packet describes one requirement, retained finding, scope obligation or test
oracle. `validate` requires exact fields, unique evidence identities, relative
paths, SHA-256 hashes, exact excerpt line spans and complete requirement/finding
mappings. Each mapping includes requirement, source, assertion and observation
references. Every observation references a passing controller-executed check.
Both the encoded packet and actual Jev request are limited to 24 KiB. Rejected
packets consume no provider reservation. The controller retains the full source
and raw observations separately.

The caller must construct references from verified files and executions. The
engine verifies excerpt bytes and structural coverage; it cannot infer that an
excerpt contains all relevant source or that a supplied full-file hash reflects
an actual file. In particular, scope and oracle questions require the complete
relevant scope and assertion context. Missing or clipped context must not be
presented as comprehensive evidence. Split obligations only when each remains
independently answerable; otherwise block or request a focused independent review.

## Evaluation and authority

`Engine.decide` sends only the packet. A score at or above 0.95 yields yes, a score
at or below 0.05 yields no, and intermediate scores yield abstain. These defaults
are policy thresholds, not a claim of calibrated confidence. The configured model
must be a concrete identity, not a `latest` alias, and the returned identity must
match exactly. Deployment policy must reject any other mutable aliases.

Abstention and high-risk packets require an independent review callback. Stable
sampling selects both positive and negative decisive answers for shadow review.
A contradiction blocks adoption; a missing reviewer does not silently approve.
The callback must enforce an independently configured reviewer identity before
returning evidence references. Manual acceptance and operator authorization are
not supported semantic question kinds.

## Persistence and allowance

The caller holds an exclusive lease covering the cache directory and allowance.
`reserve(kind, request_id, request_bytes)` admits and records each dispatch;
`finish(reservation, outcome)` accounts its completion. The engine never grants
allowance. It persists an unresolved record before dispatch, and interrupted
reservations cannot automatically relaunch on restart.

The cache key binds the authorized session identity, exact packet, rubric,
threshold/sampling policy and evaluator configuration. It excludes broad ticket
state so unchanged obligations can be reused across gates within the same
authority. Both negative and uncertain results are retained. Changed inputs,
policy, evaluator identity or authorization produce distinct records. The caller
must independently decide whether a new request is authorized; a new cache key
is not permission to call a provider.

## Verification and limits

`tests/test-decision-engine.py` uses synthetic transports and reviewers. It covers
reuse, negative retention, escalation, contradictions, changed inputs, pending
reservations, malformed evidence, payload limits, model identity, stable sampling
and forbidden approval questions. `tests/test-jev-evaluation.py` continues to test
the existing shadow evaluator separately. Synthetic results do not establish live
model accuracy, calibrated thresholds, latency or billing savings.

## Recovery integration

See `docs/DECISION-RECOVERY.md` for controller authority, the explicit evidence
plan, separate allowance, CLI/browser operation, and deployment prerequisites.
`docs/DECISION-VALIDATION.json` records synthetic request measurements only.
The controller revalidates raw decision artifacts before adoption and in later
views; changing or losing a packet or provider response invalidates the decision.

The transport and probability-valued noul format follow the official
[Typesafe API](https://docs.typesafe.ai/api) and
[noul primitive documentation](https://docs.typesafe.ai/primitives/noul).
Thresholds and review policy above are controller policy, not provider accuracy guarantees.
