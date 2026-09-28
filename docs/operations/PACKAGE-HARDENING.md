# Package execution safety and integration status

## Implementation

This follow-up uses the package implementation from PR #82 and carries forward
the retry-admission implementation from PR #80. It does not introduce a second
graph controller. Retained Git metadata must belong to the isolated child;
redirect files, symlinks and unexpected source files during materialization block
execution. Synthetic checkpoint commits disable inherited hooks and signing.

Graph bindings include input file modes. Materialization and imported-input
refresh preserve modes and refuse changed operator content. Child scenario IDs
must cover the child's declared requirements. This is a structural prerequisite;
independent semantic challenge remains required. Ledger size is checked before
replacement so an oversized write cannot make retained evidence unreadable.
Parent usage includes preparation calls made after graph authorization. Admission
checks their sum with reserved child allocations. Authorization and graph execution
hold the preparation lease, blocking concurrent preparation before dispatch.

Existing ledgers without the new mode evidence are not migrated implicitly.
They remain retained and require explicit reconciliation. No live ticket has
been migrated or restarted.

## Endpoint and remaining acceptance

The graph endpoint is a reviewed isolated integration workspace, pending manual
acceptance. It does not mean that outputs have been integrated into the caller's
checkout, committed, published or accepted. Subsequent delivery must identify and
revalidate the exact selected workspace and output set.

PR #82 remains the implementation foundation. The alternative contract and
parent-integration scheduler are retained in isolated branches as review evidence,
not a second canonical runtime. Autonomous creation of child artifacts,
conflict-safe concurrency, complete reconciliation and endpoint certification
remain open under #67 and its dependencies. No merge or installed activation has
occurred.

## Validation

All providers are synthetic and all repositories disposable. Browser/launcher
parity exercised actual Chromium 153.0.8010.12 with 14 executable calls and zero
additional calls on replay. Packet bytes totaled 29,108; measured worker time was
4.973507499991683 seconds. Unknown calls and remaining reserved seconds were zero.
The per-call request and packet sizes are retained in
`PACKAGE-HARDENING-VALIDATION.json`. Token usage, provider-cache use and billed
cost are unknown. These measurements do not establish semantic accuracy or live
latency savings.

Ten new independent adversarial cases passed in 46.253 seconds. After the final
lease fix, five focused cases passed in 32.091 seconds, including a second
controller attempting preparation during child execution. The retained suite
contains eleven cases. They cover
Git redirection, unexpected seeds, modes, child requirement coverage, later
unknown preparation usage and overflow preserving readable evidence.

Twelve existing independent controller cases passed in 85.991 seconds. Six
retained retry-admission cases passed in 22.415 seconds. Contract cases cover
structural rejection. The accounting fixture now asserts the sum of synchronized
worker observations without comparing it with filesystem/scheduling wall time.

Five package controller cases passed in 84.960 seconds before the final admission
and lease fixes; the successful full graph, admission and lease boundaries were
rechecked by the final focused cases and browser journey. Twenty-four shared
operation cases passed in 75.462 seconds. Temporary installation of exact revision
`562284e786448bc0ea6d6994369670d439163cdd` passed in 14.348 seconds with four
synthetic calls, seven reused operations and no repeated calls. It is foundation
installation evidence, not an installed package-browser certification.

Independent code review approved controller SHA-256
`0fca9af52203046f24161057babfaaeba0513a35c28b1cc8e0e734666544c8c1`.
Earlier local trials that overlapped source edits invalidated their own bindings;
they are superseded, not passing final evidence.

## Convention verification

- Installed names retain the prefix; shared roles and provider routing stay neutral.
- Upstream issue authority and local ledger identity remain distinct.
- Existing package, retry, operation and browser fixtures exercise changed boundaries.
- The existing trajectory contract is unchanged.
- MEX claims cite source files; graph-index grounding is unavailable.
- Broader acceptance and live endpoint readiness remain explicitly unverified.
