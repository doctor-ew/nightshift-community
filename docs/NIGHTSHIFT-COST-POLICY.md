# Authentication and usage policy

The terminal factory launcher defaults to subscription authentication. Hosted
API billing requires explicit per-run --auth api; do not use it as a workaround
for expired login or exhausted subscription usage.

Each participant uses their own authorized account. Subscription access is not
unlimited and does not disable provider-account extra usage. Check account
settings and event arrangements separately. Never share keys or session tokens.

The launcher removes selected inherited billing credentials and checks hosted
login status. This is not an account-wide spending firewall or a guarantee about
arbitrary subprocesses, credential helpers or directly launched coding sessions.
See scripts/nightshift-factory.sh and tests/test-factory-auth.sh for implementation
and mocked regression coverage.

Local inference is optional and experimental in this pilot. Missing usage or
cost information means unknown, not zero. Do not weaken tests, security policy
or independent review to stay within a usage budget.

## Accounting meanings

Nightshift keeps three cost fields separate:

- `provider_reported_estimate_usd` is a provider CLI or client-side estimate. It is
  provenance-bearing but is not an invoice.
- `token_derived_estimate_usd` is populated only when a versioned pricing source and
  an exact provider-reported model identity are available. A routed or selected model
  name is not sufficient.
- `actual_billed_usd` is populated only from an authoritative billing receipt.

These values are never merged or substituted for one another. A missing field stays
`null`; it does not become zero. Known token or estimate subtotals may be reported
while `complete` is false.

Ticket accounting is isolated by the canonical tuple `source`, `repository`, and
`source_id`. Direct ticket work contributes only to that tuple. Shared batch
orchestration and unattributed work are retained as provenance but are not allocated
across tickets. Failed calls, retries, repairs, resumes, and interrupted runs remain
accounting observations regardless of engineering outcome.

Claude `total_cost_usd` and per-model `costUSD` values are client estimates. Claude
main-loop `usage` excludes SDK-internal subagents, while inclusive `modelUsage` and
reported estimates can include them. Codex reports token usage on `turn.completed`
events but does not report model identity there. Consequently, Codex token totals can
be known while token-derived cost remains unknown.
