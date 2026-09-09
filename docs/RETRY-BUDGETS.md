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
