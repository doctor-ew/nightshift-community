# Codex-first routing

Codex is the default role provider. Gears 1–3 use the existing configured Codex model. Gear 4 retains each role's configured Claude delegate. Independent review uses author provenance: Codex-authored work routes to Claude; Claude-authored work routes to Codex. Delegation is explicit routing, not an automatic retry through another provider after an error.

The launcher already defaults to Codex when no runtime is selected. Existing explicit project overrides and the opt-in Claude-only policy remain supported; prior ticket receipts and budgets are retained. The explicit workshop profile remains separate from standard routing.

All UI work remains in scope. This change modifies routing only; it does not remove or revert UI implementation, evidence, or the broader controller work. Azure AI Foundry is an operator-approved runtime target. This change does not implement a Foundry adapter, select an Azure deployment, or authorize an automatic switch to API billing.

Verification: `tests/test-codex-first.py` covers primary/delegate selection, independent reviews in both directions, and retained explicit Claude-only compatibility. `tests/test-provider-policy.sh` covers policy inheritance and invalid/conflicting routes. No live model invocation is required for these checks.
