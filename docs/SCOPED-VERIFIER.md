# Scoped verifier authorization

Factory orchestration may call the shared role dispatcher, including its read-only
Codex subprocess for independent verification of Claude-authored work. Direct
Codex launches and recursive factory/orchestrator launches remain prohibited.
Existing authentication, provenance and schema validation remain authoritative.

The dispatcher marks child processes with NIGHTSHIFT_ROLE_CHILD=1. Both launcher
and dispatcher reject re-entry under this marker before setup or provider work.
This is defense against accidental recursion, not an adversarial security sandbox:
a process able to clear its environment or invoke a provider directly can bypass
it. Codex verifier read-only sandboxing remains in the existing dispatch command.

This change resolves the contradictory blanket prohibition that blocked issue #8.
It does not add transport timeout/output quotas; those parts of #15 remain open
and must not be represented as enforced by this environment marker.
