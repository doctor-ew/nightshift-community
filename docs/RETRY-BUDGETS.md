# Adversarial retry budgets

The adversarial stage uses the bounded dispatcher, which invokes the existing
role dispatcher and atomically records a shared budget in the task output directory.
Infrastructure failures have a cap of three. Substantive failed evaluations have
a cap of four (initial evaluation plus three repairs). All calls, including success,
share a twelve-invocation ceiling across source and claim batches. A successful
transport with conflicting claims is a substantive failure, not gate approval.

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
