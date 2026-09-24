# Approved implementation plan

The controlling session approves this plan under the user’s explicit authorization to complete issue 35 autonomously. No further user approval is needed for a read-only patch proposal.

Blast radius: the seven source/documentation paths allowed in implementation.in.md; persistent metrics, provider parsing, dispatcher/factory capture, ticket attribution and documentation. Existing run CLI consumers remain compatible.

Sequence: implement typed parsing; extend immutable receipt ingestion and deterministic ticket replay; connect trusted identity and captured usage at dispatcher/factory boundaries; document reports and unknowns.

Risks: duplicate/overlapping usage, incomplete provider data and accounting I/O failures. Mitigate through identity deduplication, explicit unknown coverage, immutable allowlisted receipts and nonfatal boundaries. No routing/authentication/gate changes. Size: Moon.
