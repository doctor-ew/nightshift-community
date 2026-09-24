# Spec-writer input — task 46

## Ticket

External ref: gh-46
Title: Extend setup wizard with provider and connection readiness checks
URL: https://github.com/doctor-ew/nightshift-community/issues/46
Source: gh (state: open)

Body:
# Extend setup into a connection-validation wizard

## Problem
New developers can save setup settings but only discover missing provider login, unavailable tools, incompatible review routes, or ticket/Git credentials after starting work. Extend the existing setup wizard to report readiness before a factory run.

## Scope and acceptance criteria
- Extend the existing terminal setup path, preserving model-free init and existing noninteractive behavior.
- Detect supported installed tools for Claude, Codex and local/Ollama execution. Show missing tools and actionable next steps; do not install tools automatically.
- Let users choose permitted providers with existing standard and Claude-only policies. Explain coordinator versus role routing and validate all selected routes against policy and installed capabilities. Do not invent new provider support.
- Check provider authentication through documented available mechanisms without printing, recording, or copying credentials. Distinguish authenticated, missing, unsupported/unverified, and failed checks. Never silently switch to API billing.
- Model names/access must not be guessed. Use non-generative discovery when supported; otherwise report model access unverified. Default setup must not invoke a model. If a smoke test is offered, it must require explicit separate opt-in, identify potential billing, and respect provider policy.
- Validate configured ticket-source access separately from Git-host access. Use bounded read-only checks for supported integrations; unsupported checks must be reported as unverified, never ready. Do not require credentials for sources or publication modes the user did not select. Local Markdown must work without remote credentials.
- Present a readiness summary showing effective coordinator, role/reviewer providers, selected source, publication readiness, actionable blockers and unverified checks. Persist only nonsecret configuration and sanitized diagnostic results if needed. Do not claim end-to-end model readiness from CLI presence alone.
- Preserve existing project settings, aliases and unrelated files; avoid corrupting configuration on cancellation/failure. No writes to upstream tickets, no remote repository changes during setup.
- Add deterministic tests with fake CLIs/network responses covering happy path, missing tooling/authentication, incompatible routes, timeouts, malformed output, secret redaction, and model-free operation. Document the new onboarding flow and limitations.

## Exclusions
No Gemini, Grok, or Foundry adapter in this ticket. No generic plugin marketplace, browser wizard, model benchmarking, automatic credential collection, or policy gateway redesign.

## Delivery
Use Nightshift's canonical engineering stages, role dispatcher, evidence gates, bounded repairs and accounting. Build from origin/main in an owned isolated worktree. Preserve unrelated changes in the source checkout. Push verified work and open a PR against main. Do not merge or deploy. Verify actual source identifiers before implementation; the prose above describes requested behavior rather than a predetermined implementation.

## Ledger metadata

bd_id: (none — this run uses file-ledger mode; no beads database is initialized in this environment)
external_ref: gh-46
source URL: https://github.com/doctor-ew/nightshift-community/issues/46

## Engineer Notes

Intent: Extend the existing non-interactive `nightshift-setup.py` / `nightshift-setup.sh` setup path so it also probes and reports environment readiness — installed provider CLIs, provider auth state, ticket-source reachability, and route validity against policy — before a factory run, without inventing new provider adapters or auto-installing/collecting credentials.

Hidden constraints: Must not break existing non-interactive/model-free `--defaults`/`--read` init paths (`nightshift-setup.py`) or the additive-lossless config-write contract already covered by its schema validation. Must not invoke a model by default (no billing surprises), must not print/store secrets, and must reuse `nightshift-capability.sh` (tool detection) and `nightshift-credentials.sh` (auth check) conventions rather than duplicating them.

Blast radius: `scripts/nightshift-setup.py`, `scripts/nightshift-setup.sh`, `scripts/nightshift-capability.sh`, `scripts/nightshift-credentials.sh`, and any new readiness-summary script/tests under `tests/`. Possibly `docs/` for onboarding documentation of the new flow. No changes expected to the pipeline commands (`commands/nightshift-*.md`) or agent role prompts (`agents/`).

## Product spec context

None provided — proceeding with `--override` (no product spec/PRD airlock for this ticket; engineering ticket is self-contained).

## Extractor results (nightshift-code-fact-extractor, EXTRACTOR_RUN below)

EXTRACTOR_RUN: SEE docs/46/product-extractor.out.json (generated just prior to this delegation)

Status: SUCCESS — all 9 submitted identifiers verified (see docs/46/product-extractor.out.json for full claims: file, line, inspected_files per identifier). Verified identifiers:
- scripts/nightshift-setup.py (line 1) — exists as executable Python script
- scripts/nightshift-setup.sh (line 1) — exists as executable shell script
- scripts/nightshift-capability.sh (line 65) — exists with --has and --resolve flags
- scripts/nightshift-credentials.sh (line 1) — exists as executable shell script
- nightshift-capability.sh --has <tool> (line 158) — query mode, 0/1 exit code
- nightshift-capability.sh --resolve (line 21) — semantic adapter lookup via Python
- routing.json (line 1) — provider envelopes (claude, codex, local) + role routing with gears
- providers.policy (line 61 of nightshift-setup.py) — accepts 'standard' or 'claude-only'
- ledger.mode (line 77 of nightshift-setup.py) — accepts 'auto' or 'files', defaults 'auto'

No graphify graph.json — graphify was not run for this task (not on PATH check was not performed; skip per instructions when absent).

## Required spec output — inject verbatim

**REQUIRED — every spec must include these two final sections:**

### ## Model Router
Count the Files to Change table. Apply the decision tree:
- ≥ 3 files OR ≥ 2 top-level modules → **Opus / Enterprise Architect**
- Architecture or design decision? → **Opus**
- Shared contract change (API, DTO, hook signature)? → **Opus**
- Otherwise → **Sonnet / General Engineer**

Write the decision as a filled line: `**Decision:** Sonnet / General Engineer`
A bracket placeholder `[ ]` will be blocked by the spec-guardrail hook.

### ## Sources
List every file read to support a factual claim. Format per entry:
`repo-relative/path/to/file.ext:LINE_START-LINE_END` (branch: BRANCH, commit: SHORT_SHA) — what this confirms
Line numbers required. Branch required. Commit SHA (`git rev-parse --short HEAD`) required.
Vague entries ("see file") are invalid. The spec-guardrail hook blocks the Write if Sources
is absent or has no `path:line ... commit:` entries.

Current branch: nightshift/46
Current commit: d05fbca
