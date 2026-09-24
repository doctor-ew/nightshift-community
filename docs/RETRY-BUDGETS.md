# Adversarial retry budgets

The adversarial stage uses the bounded dispatcher, which invokes the existing
role dispatcher and atomically records a shared budget in the task output directory.
Infrastructure failures have a cap of three. Substantive failed evaluations have
a cap of four (initial evaluation plus three repairs). All calls, including success,
share a twelve-invocation ceiling across source and claim batches. A successful
transport with conflicting claims is a substantive failure, not gate approval.

The dispatcher returns zero for a valid report, leaving its reservation pending.
Its `<output>.retry.json` sidecar identifies that attempt and its unique retained
result. The canonical adversarial stage checks completeness and evidence, maps
`NOT_FOUND` plus spec-authored `[NEW]` to accepted `NET_NEW`, and finalizes the
same attempt with the accounting CLI as `success`, `substantive`, or `schema`.
Raw extractor statuses never decide whether a new symbol is an error. Finalizing
does not count another call. Pending reports block further launches until mapped;
a zero transport exit never approves a gate. Source evaluation must be finalized
before the claim batch starts. See `commands/nightshift-adversarial.md` for the
finalization recipe and authoritative mappings.

Reservations are recorded before provider launch under an invocation lock. An
interrupted pending reservation blocks further dispatch until explicitly reconciled;
never delete/reset its budget merely to retry. Prior outputs have unique retained
paths. Repeated ingestion of an identical attempt is idempotent.

Unsupported model errors outrank incidental MCP authentication noise. An unchanged
rejected routing-file fingerprint is not launched again, even when the attempt or
output path changes. This conservative check requires a routing-file change.
A changed configuration
does not establish access: the provider still validates subscription authentication.
There is no automatic switch to API billing. Auth, schema and unknown failures
require diagnosis rather than automatic fallback. Final independent review remains.

This accounting is scoped to adversarial calls using the documented bounded entry.
It is not a hostile-process sandbox, a global controller migration, or a transport
timeout/output quota implementation. Those separate #15 limits remain outstanding.
The existing stricter malformed-response reissue cap still applies.

## Repeated registered repair inputs

For a task with `repair-checks.json`, source-review admission first requires the
original snapshot to fail and the current artifact to pass the registered checks.
The dispatcher then hashes the sorted artifact paths, JSON pointers, and canonical
JSON content hashes. It persists that signature against the reserved attempt in
`.adversarial-budget.json` before dispatch.

A signature already finalized as `substantive` cannot launch another review.
Changing JSON whitespace, object key order, finding IDs, routing, or the report
filename does not count as a repair. Refusal consumes no additional reservation.
Pending attempts and exhausted budgets retain their existing restrictions;
infrastructure failures remain independently retryable within the original limits.

`repair-admission.json` exposes `needs-decision` and an actionable unblock path
through the dashboard's existing gate reader. Inspect the retained finding, change
the repair author/provider within policy, and correct the relevant artifact or
regression contract. On later admission the status becomes `skipped`, meaning the
admission guard passed; it never approves the source or behavioral gate.

This guard detects identical registered artifact content after a substantive
failure. It does not detect semantically equivalent findings on changed artifacts,
enforce provider switching, backfill historical signatures, or cover reviews that
bypass the bounded source dispatcher. Artifact content changes are necessary for
re-admission of the same registered targets; they are not proof of correctness.
