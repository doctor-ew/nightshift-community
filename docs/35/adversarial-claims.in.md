Read-only independent technical claim review of Codex SPEC. Do not dispatch any role/factory or write files. Return exactly one ordered claim per numbered entry, with file,line,inspected_files evidence. [NEW] not found maps to valid NET_NEW; never assert exists. For external facts use verified primary source (URLs in SPEC), do not conflate current code with intended change. Full scope/spec and receipt contract are in docs/35/SPEC.md; report any genuine requirement contradiction.

1. [EXISTING] Current metrics cmd_init creates run context and immutable observation event files with atomic summaries, with no ticket tuple in current observation schema.
2. [EXISTING] Current run metrics captures input_tokens/output_tokens only and uses reported_model null.
3. [EXISTING] Current _summary deduplicates within one run by invocation_id and repair tuples.
4. [EXISTING] Current dispatcher Claude extracts result usage and Codex requests JSONL but reads only final structured contract for completion.
5. [EXISTING] Current factory emits own observation on normal completion/interruption and exports run context.
6. [EXISTING] Current GitHub adapter emits external_ref gh-number without repository identity.
7. [EXISTING] Current metrics stage allowlist drops unknown stages; unknown usage is not zero per policy.
8. [EXISTING] Claude authoritative cost tracking says result usage excludes SDK subagents, modelUsage and total_cost_usd include them; estimates are client-side not invoices.
9. [EXISTING] Codex TurnCompletedEvent usage has input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens and no reported model; verify cached-total semantics against primary source.
10. [NEW] Add scripts/nightshift-provider-usage.py and tests/test-ticket-accounting.sh; no existing file collision.
11. [NEW] Add ingest, ticket-report, normalized receipt fields and ticket-metrics persistence described in SPEC Guardrails; these are requirements, not assertions of present implementation.