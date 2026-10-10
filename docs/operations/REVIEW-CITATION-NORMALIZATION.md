# Review citation normalization

The recovery adapter accepts exact evidence IDs with surrounding whitespace or
colon annotations. For example, `source: explanation` resolves to `source` only
when that packet has one matching identity. This deterministic conversion adds no
model call. The original dispatcher response remains retained; validation operates
on a separate normalized view.

Unknown or ambiguous IDs, duplicates after normalization, changed hashes, missing
evidence roles and invalid reviewer identity remain invalid. Normalization does
not change the verdict, authorize work, reset budgets or revisit failed receipts.
The implementation is provider-neutral and does not depend on Beads.

The focused dispatcher fixture tests annotated responses through all recovery
gates with the same call count as exact IDs and checks that raw annotations remain
retained. Local tests cover unknown/ambiguous references, duplicate references,
stale hashes, input preservation and negative/abstaining verdicts.

This change handles citation presentation, not arbitrary document parsing. Future
format and provider adapters must feed the same evidence contract. Routine
normalization belongs in deterministic code; substantive reasoning and independent
review remain configurable model work. No Foundry integration or live certification
is claimed here.
