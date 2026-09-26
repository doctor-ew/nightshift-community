# Guided intake

## Supported profile

The dashboard can start a fresh qualified GitHub reference or project Markdown reference without preparing controller files in a terminal. `scripts/nightshift-intake.py` owns source resolution, persisted product questions, bounded draft preparation and exclusive artifact creation. The browser and `nightshift intake --project DIR --request FILE` use the same API. A request file contains an action and its exact arguments; `--request -` reads JSON from stdin.

Supported references are `gh:owner/repository#number` and `spec:project-relative.md`. Other existing source adapters and configurable provider routes retain their existing entrypoints; this initial intake profile does not claim guided support for them.

The operator supplies files in scope, existing rules and architecture guidance, a verification script and interpreter, and required acceptance behavior. Missing choices become one retained question through the existing decision ledger. Answers do not start continuation workers. Exact answered records reach the authored request and specification for subsequent independent review.

The preview contains the proposed plan and exact artifact text. Default ceilings are 16 provider calls, 600 execution seconds and 900 wall seconds; each operation remains bounded separately. Existing routing and provider policy select workers. Jev is disabled in the initial plan, and substantial independent review remains part of the existing operation recipe. The endpoint is the actual local checkout and branch; intake does not create a branch, publish, merge or deploy.

## Authority and preservation

Resolution, readiness, questions, preview and artifact creation launch no model. Artifact creation does not create operation authority. The operator then selects and authorizes the existing independent operation or bounded recipe.

Draft bindings include the normalized source snapshot, declared input bytes and modes, configuration hashes, decision records, generated artifacts and intake implementation. Materialization rechecks those bindings and preflights every destination. Directory-descriptor traversal rejects parent links; final writes are exclusive. A retained journal allows a completed write to survive a crash without replacing it. Different bytes, modes, unowned files or a raced destination remain conflicts. Cancellation retains the journal and files and prevents implicit resumption. Cancellation after materialization belongs to operation lifecycle control.

Runtime identity distinguishes the serving checkout from the resolved installed runtime. Unknown or modified revisions remain explicit. Readiness reports source, manifest, routing and tool observations. Authentication/model access remains **unverified** when no evidence exists; executable presence is not authentication. This does not complete the separate connection-readiness work in #46.

## Validation and status

Independent backend review passed 21 synthetic tests in 13.787 seconds, including stale evidence, conflicting source identity, altered retained drafts, namespace isolation, cancellation, partial-write recovery, symlink substitution and raced operator files. Backend SHA-256: `5a59f47b52b6b7732eaecb5471e64f585132b9a27526a7bd5e17d8eb419fac1a`.

Three actual CLI/HTTP tests passed in 12.271 seconds. Eleven existing server tests and fourteen dashboard model tests passed. The actual Chromium/launcher flows for both supported sources are recorded separately with exact revisions, request sizes, call accounting and replay receipts.

Implementation is a focused guided local-checkout profile. Integration requires the dependency PR stack and current checks. Complete #69 acceptance, other source profiles, authenticated endpoint certification and live activation remain open. No live providers, real-ticket restart, live allowance, installed-runtime change, merge or deployment is part of this validation.

Actual browser acceptance at `129ea795ce0543d158110c170a2c2168c60cb4be` passed both supported-source journeys and bidirectional mutation blocking between intake and operations. Each used four synthetic calls and replayed seven operation receipts with zero additional calls or unknown usage. Local packet bytes totaled 4,475; GitHub packet bytes totaled 4,459. Worker time measured 1.4790247919991089 and 1.42214187600257 seconds respectively. Per-call argv sizes, packet sizes and exact source hashes are in `GUIDED-INTAKE-VALIDATION.json`. Tokens, provider KV-cache reuse, billed cost and independent reviewer usage remain unknown.
