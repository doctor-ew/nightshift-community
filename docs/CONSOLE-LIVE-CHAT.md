# Live progress and ticket chat

The ticket card has two separate views: **You are here** reports verified process
activity, while the numbered timeline reports recorded gate outcomes. An active
repair does not erase a previous failed gate or establish that a gate passed.

The live panel includes role, provider/model, attempt when recorded, elapsed
time, latest recorded update and its age, and whether an operator should inspect
the outcome. Process identity checks include the command and start time. Activity
is not a guarantee of useful progress; a quiet worker is not automatically declared
stalled. Token totals still follow usage receipts, not a live token stream.

## Ask about this ticket

Expand **Ask about this ticket**, select a provider, and ask a question. Answers
are based on a bounded snapshot of public ticket evidence and current activity.
Source IDs in an answer map to the displayed source labels. Chat cannot modify
files, approve gates, steer workers, resume the pipeline, or trigger repairs.
Use the separate recovery controls for those operations.

Claude uses the existing first-party subscription login with tools, MCP servers,
skills, and session persistence disabled. Local chat calls the configured loopback
OpenAI-compatible endpoint with no tools and a JSON schema response request.
Both routes validate the response and its source IDs. This validates source
membership, not the semantic correctness of every model claim.

Codex chat is explicitly unavailable until a tool-free CLI execution mode can be
verified. Selecting a configured default that resolves to Codex returns an error;
there is no silent fallback. Choose Claude or Local explicitly in that case.

Routing reads the ticket worktree's `routing.json`. The optional
`roles.nightshift-ticket-assistant.gears.1` entry defines the chat default;
otherwise the engineer's gear 1 is used. Explicit provider choices use configured
models, and local uses `local.model` first. Existing `claude-only` policy remains
enforced. API-authenticated browser chat is not enabled.

One answer may run per ticket at a time, with a 120-second worker deadline.
The bounded conversation is retained locally under the repository's Git common
directory at `nightshift/console/<task>.chat.json`. Private evaluation cases,
raw provider transcripts, and credentials are excluded from the evidence bundle.
Requests require the dashboard's same-origin checks and per-server token.

## Verification

Automated checks cover process identity, stale records, ticket isolation, bounded
evidence reads, local endpoint selection, response schema, citation membership,
worker concurrency, subscription flags, and HTTP request boundaries.

On September 20, 2026, the running dashboard at port 57867 was checked in a browser.
Real chat requests completed with Claude/Haiku and local
`Qwen3-Coder-30B-A3B-Instruct-4bit` through oMLX. The initial local request returned
malformed JSON; the adapter was changed to request a structured response, and the
subsequent request passed validation. This is a chat smoke test, not proof that
the Jobs Night product or its pipeline gates have completed.
