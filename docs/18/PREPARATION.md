# #18 / #19 — implementation preparation, not a stage approval

Handoff preparation only. Kept separate from the #13 design PR.
Packaging update: #8 is now merged; this handoff includes integration revision
`bd47c2ab031d83e011e443c82611983614897935`. The inventory below is historical
and must be re-grounded against that implementation before edits.
Inspected remote integration HEAD: `bea0b3935f03a10e3c50b9db391039e1d85d76ad`.
Upstream scope: [#18](https://github.com/doctor-ew/nightshift-community/issues/18),
[#19](https://github.com/doctor-ew/nightshift-community/issues/19).
Actual implementation waits for #8 verification/merge and re-grounding of the
overlapping files listed below. No providers, installed runtime or Coach were changed.

## Verified coupling inventory at the inspected commit

| Area | Evidence | Required treatment |
|---|---|---|
| Test command priority | `agents/nightshift-run-all-tests.md:20-50` prioritizes legacy convention file, then lockfile/manifest heuristics, blocks ambiguity and preserves exact flags | One explicit neutral convention decision, not scattered rewritten prose. Preserve legacy-only behavior. |
| Other role conventions | `agents/nightshift-engineer.md:77,85`; `agents/nightshift-architect.md:115`; `agents/nightshift-spec-writer.md:37` | Reference shared resolved conventions; do not replace legitimate provider routing. |
| Review executor | `commands/nightshift-review.md:17,169` names one provider and legacy convention file | Describe the active runtime and shared convention result, keeping quality lenses/gates. |
| Optional document capability | `commands/nightshift-product.md:178-198`, especially `:189`, names a provider-specific MCP method | Resolve a semantic document-read capability through a configured runtime adapter; retain optional fetch-failure behavior. |
| Project root | `commands/nightshift-eng.md:93,167`; `commands/nightshift-implement.md:41,50`; batch `:124-127,175-184,237-261` | Translate old adapter context at ingress, then use a neutral resolved project root; preserve controller/ticket-root separation. |
| Script context | `scripts/nightshift-state-dir.sh:12-32`; scoped search found 21 legacy-project-variable matching lines under scripts | Inventory every caller before changing fallback semantics; no broad text substitution. |
| Deployment conventions | `commands/nightshift-deploy.md:39-45` | Preserve explicit deploy JSON precedence and legacy compatibility; add neutral convention lookup without changing production authorization. |
| Stale branding not covered by current exact-name patterns | `commands/nightshift-adversarial.md:350` cites an unavailable legacy ADR | Replace with a verified local rationale/reference, not a fabricated equivalent ADR. |

This inventory is scoped to the referenced checkout. It is not an installed-user-
plugin, secrets, all-history or employer-history audit.

## Existing precedence / behavior that must not silently drift

1. Launcher defaults project to current directory and explicit `--project` replaces
   it (`scripts/nightshift-factory.sh:76,91-94`). Existing stage/state helpers start
   with adapter-provided project root, then Git root, then cwd; helper `--project`
   overrides that (`scripts/nightshift-state-dir.sh:12-32`). These differ today.
2. `.nightshift.toml` wins when present; otherwise `nightshift.toml`
   (`scripts/nightshift-manifest-path.sh:3-10`). Setup chooses the same canonical file
   and parses it with tomllib (`scripts/nightshift-setup.py:19-32`). Do not create a
   third config path or overwrite an unreadable canonical file with a fallback.
3. Current test role uses exact legacy-file command/flags first, then the listed
   language/package-manager order, and blocks if ambiguous. Preserve runner versus
   package-manager distinctions and the no-added-flags rule
   (`agents/nightshift-run-all-tests.md:20-50`). The current manifest defaults define
   no test-command key (`scripts/nightshift-setup.py:34-40`); any new setting is a
   proposed schema addition, not an existing contract.
4. State lookup prefers a canonical per-task tracker, then legacy locations;
   shared operations retain all-legacy state until canonical state exists.
   `--create` has explicit side effects (`scripts/nightshift-state-dir.sh:33-65`).
   Neutral project discovery must not “migrate” this state during read-only checks.
5. Deploy lookup is canonical deploy JSON, legacy deploy JSON, conventions, then
   platform heuristics (`commands/nightshift-deploy.md:39-45`). Do not reinterpret
   neutralization as authorization to deploy or alter that JSON priority.
6. `nightshift-capability.sh` already owns optional CLI probing and caching;
   `--has` / `--which` are existing interfaces. Its cache is 24 hours, probes can
   create its cache directory, and its key set is explicit; it does not discover
   arbitrary runtime MCP methods (`scripts/nightshift-capability.sh:8-22,36-60,97-123`).
   Preserve existing key semantics and keep #8's deterministic preflight read-only.

## Smallest recommended shared abstraction (proposed, not implemented)

**One project-context/convention resolver, one existing capability owner.** Avoid a
large plugin framework or parallel resolvers in every agent/command.

- Extend shared project discovery with a pure/read-only normalized context result:
  canonical project root, scoped convention file paths, selected test command and
  its origin, deploy-convention reference, conflict diagnostics. Explicit project
  argument wins; proposed neutral environment variable follows; legacy adapter
  value is accepted as an ingress fallback; Git root/cwd are final fallbacks.
  When both environment values differ without an explicit project argument, fail
  with a conflict rather than silently run in a different repo. Explicit argument
  precedence remains deterministic and reported. Name/version this new interface
  during implementation; no new variable/flag is claimed available here.
- Prefer applicable scoped AGENTS.md conventions, with legacy convention-file
  fallback only where the neutral convention source is silent. A newly supported
  explicit configured test command is selected only after validation against
  applicable instructions; conflicting explicit commands produce a diagnostic
  and block instead of silently weakening instructions. Legacy-only repos retain
  their existing exact command. Ambiguous multiple lockfiles remain blocked.
  Record selected origin and ignored fallback; document this precedence change
  visibly rather than treating it as a cosmetic rename.
- Do not implement arbitrary prose parsing as trusted command execution. Resolver
  reports convention paths and validated configured command when available;
  runtime reads applicable prose as instructions and reports a selected command
  with provenance. Existing policy remains the execution authority. Explicit
  scoped commands and fixture assertions prevent heuristic runner substitution.
- Extend the existing capability boundary only for a semantic document-read
  operation backed by an adapter-provided/configured, validated mapping. The core
  asks for the operation, not a provider-specific MCP function. Provider-specific
  names remain in adapters. An absent optional capability returns unavailable and
  preserves the current product airlock's warning/empty-context fallback. Do not
  require a new online discovery probe or shared cache write during #8 admission.
- Use resolved root consistently when moving into ticket worktrees and returning
  to controller state. Legacy environment translation belongs at compatibility
  boundaries; actual adapter auth/routing names and paths are not banned content.

## #8 overlap — mandatory re-ground after merge

Read-only observation of the active #8 spec's Files to Change table at
`/tmp/nightshift-efficiency-build-worktrees/8/docs/8/SPEC.md:174-189` lists:

| #8 file | #18/#19 impact |
|---|---|
| `scripts/nightshift-factory.sh` | High overlap: project ingress, setup/admission order and run identity. Rebase and preserve every pre-provider rejection/metrics hook. |
| `scripts/nightshift-agent.sh` | High coupling: role dispatch provenance, neutral input context and run-linked observations. Do not overwrite #8 metrics or #20 retry fixes. |
| `scripts/nightshift-worktree.sh` | Read-only admission/ownership context; re-ground before any helper-root change. |
| `scripts/nightshift-ticket-source.sh` | Identity-only versus fetch paths; capability resolution must not force network fetch during preflight. |
| `scripts/nightshift-preflight-check.sh`, `scripts/nightshift-baseline-check.sh` | Proposed in #8; inspect final installed behavior after merge, not provisional working contents. |
| `scripts/nightshift-run-metrics.py`, `scripts/nightshift-retry-increment.sh` | Preserve run/task/project identity and observed repair counts; no new context field without schema agreement. |
| `tests/test-factory-auth.sh`, `tests/test-agent-dispatch.sh` | Shared fixture dependency lists will change; extend instead of replacing. |
| `tests/test-factory-preflight.sh`, `tests/test-run-metrics.sh` | Add #18 context/config conflicts only after preserving #8 no-provider and privacy assertions. |

Also re-ground `scripts/nightshift-manifest-path.sh`, `nightshift-manifest-validate.sh`,
`nightshift-setup.py`, `nightshift-state-dir.sh`, `nightshift-capability.sh`,
`install.sh`, and canonical commands/roles at the actual post-#8 integration SHA.
Live #8 worktree inspection was read-only; this document is not its approval.

## #19 guard design and explicit scan boundaries

Extend `tests/test-branding.sh`, not a second disconnected scanner. Current source
scan covers root-maintained files, recursively scripts/commands/agents/skills/compat/
tests, but only top-level docs (`tests/test-branding.sh:11-29`). It checks retired
name patterns and installer alias ownership fixtures; it does not implement
provider-instruction semantics or installed-adapter content inventory
(`tests/test-branding.sh:32-49`).

Propose a reusable read-only scanner with two reported inventories:

1. **Public source:** maintained runtime core, configured docs/templates and adapter
   code as enumerated by repository ownership. No Git object/history traversal.
2. **Installed Nightshift-owned adapters:** exact install destinations / owned
   filenames and symlink targets derived from installer rules. Do not recursively
   scan entire user command/skill/plugin/settings homes. Do not follow an unrelated
   symlink just because its basename looks familiar. No install, repair or deletion
   during audit. Installer destination rules are at `install.sh:433-487`; actual
   shared/adapter target defaults at `install.sh:24-28`.

Classify retired identifiers separately from forbidden execution coupling in core.
Use a reviewed rule ID + exact path/context allowlist with rationale for legitimate
adapter/routing/auth and documented legacy-reader references; never exempt all
provider strings or all scripts. Report rule ID, relative path, line and inventory
only, not raw matching line text (which could contain sensitive values). Include
unreadable/skipped/unknown targets so “none found” cannot imply complete coverage.
Test retired identifiers via generated temporary fixtures rather than introducing
banned literal strings into maintained core. Add the guard to the existing shell
test/CI discovery and installer check/audit path; do not make audit mutate user
configuration (`.github/workflows/shellcheck.yml:24-40`, `install.sh:5-8`).

## Minimum regression matrix

| Fixture | Required result |
|---|---|
| Scoped AGENTS.md with exact test flags | Same selected command under both runtime adapters; flags untouched. |
| Legacy-only repo | Existing command and state directory behavior unchanged, with fallback provenance. |
| Both convention sources disagree | Explicit conflict, no guessed command/provider launch. |
| Explicit validated configured command | Known precedence and origin; cannot contradict required higher-level instructions silently. |
| Nested subproject plus unrelated sibling conventions | Only applicable scope considered; no global recursive convention merge. |
| Neutral/legacy env disagree; explicit `--project` supplied or absent | Explicit argument wins when present; absent argument blocks conflicting roots. |
| Ticket worktree/controller round-trip | Ticket edits remain isolated, controller batch state stays under controller root. |
| Canonical manifest unreadable/malformed; valid legacy manifest exists | Fail, no silent fallback/overwrite; canonical precedence preserved. |
| Optional document capability missing/auth failure | Existing optional fallback and reason, not provider-specific tool invention. |
| Missing baseline/spec, dirty owned worktree, conflicting context | #8 preflight remains before provider launch with preserved source/ownership. |
| Banned identifier/execution instruction in neutral core | Exact rule/path/line failure without printing content. |
| Actual adapter/model/auth reference | Pass only via precise reviewed context rule. |
| Installed owned adapter with bad content plus unrelated plugin/symlink | Owned target reported; unrelated files neither read, printed nor altered. |
| Nested maintained docs and unreadable owned artifact | Coverage explicit; unreadable is not a clean scan. |

## Handoff gate

After #8 merges: record fresh integration SHA, re-read every overlap, choose and
document the new resolver/config schema, then implement #18 and its fixture matrix.
#19 scanner/fixtures may be built in a separate isolated branch against that agreed
boundary, but integration shakedown must run after both. No #13 prototype or Coach
restart until the parent sequence reaches those verification gates. This retained
preparation does not authorize or claim any stage success.
