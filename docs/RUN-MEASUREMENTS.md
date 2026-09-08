# Run measurements

Preflight admission and run metrics are read-only/observational features added to
`nightshift-factory.sh`. Nothing described here gates independent review, regression
tests, drift checks, or the existing subscription-only auth policy — it only reports
what actually happened, or reports `null`/`unavailable` when it genuinely does not know.

## Preflight admission

Before `nightshift-factory.sh` touches its own auto-setup, dashboard, auth probes, or
any provider, it runs `scripts/nightshift-preflight-check.sh`: a deterministic,
read-only coordinator over four checks, always in this order, stopping at the first
failure:

1. **baseline** — `scripts/nightshift-baseline-check.sh` (the same predicate the
   factory itself uses; also reusable standalone).
2. **input** — ticket/local-spec identity, via
   `scripts/nightshift-ticket-source.sh --derive-id`. Explicit upstream refs
   (`gh:`/`jira:`/`monday:`/`notion:`) resolve their id straight from the ref text —
   no network fetch, no title/body. A bare bead id still requires an existing
   `docs/*/.bd-id` mapping; a missing/ambiguous mapping blocks (`TASK_UNRESOLVED`)
   rather than silently skipping the ticket. GitHub refs never require Beads.
3. **manifest** — `scripts/nightshift-manifest-validate.sh` (unchanged; only read).
4. **collision** — `scripts/nightshift-worktree.sh check TASK --project DIR`, a new
   read-only operation that shares `prepare`'s own predicates (registration, receipt
   schema, base, root/ancestry, dirty, unowned branch/target) but never creates the
   metadata directory, the task lock, or any other state. `prepare` still re-resolves
   everything itself under its own lock at the actual mutating boundary — a `check`
   result is advisory the instant the process exits.

`--branch none` skips only the baseline and collision checks (there is no worktree to
isolate); input and manifest are still checked. Any other literal branch name is
`BRANCH_POLICY_UNSUPPORTED` — the worktree layer only ever manages the fixed
`nightshift/<task>` branch, and approving a different name against that fixed
convention would be a false pass for a branch the real run would not actually use.

The coordinator prints exactly one JSON object to stdout and never runs automatic
repair, migration, or setup itself:

```json
{
  "schema_version": 1,
  "status": "ok",
  "checks": {"baseline": "pass", "input": "pass", "manifest": "pass", "collision": "pass"},
  "reason": null,
  "next_action": "start_provider",
  "tasks": ["8"]
}
```

`reason` (only set when `status: "blocked"`): `BASE_MISSING`, `SPEC_INPUT_INVALID`,
`MANIFEST_MISSING`, `MANIFEST_INVALID`, `WORKTREE_COLLISION`, `TASK_UNRESOLVED`,
`INPUT_RESOLUTION_REQUIRED` (an unexpandable batch query, or a bare ref that needs an
explicit source prefix — provide an explicit ticket list instead), `USAGE`.

Exit code mirrors the reason: `0` ok · `64` USAGE · `65` SPEC_INPUT_INVALID ·
`66` BASE_MISSING · `67` WORKTREE_COLLISION · `68` MANIFEST_MISSING/MANIFEST_INVALID ·
`69` TASK_UNRESOLVED · `70` BRANCH_POLICY_UNSUPPORTED · `71` INPUT_RESOLUTION_REQUIRED.

Rejected admission never automatically invokes setup. Run `nightshift setup`
explicitly to configure an incomplete project, then retry admission.

The top-level provider has its own observation with unknown usage when its output
is opaque. Child usage remains available per observation but is not presented as
a complete run total. Model fields are routing-validated selected identifiers;
`reported_model` remains null without a provider-reported identity.

## Run metrics

`nightshift-factory.sh` creates one run-scoped, private metrics context per invocation
via `scripts/nightshift-run-metrics.py init`: a random `run_id`, a monotonic start
time, and (when a Git repository is present) a private directory
`<git-common-dir>/nightshift/runs/<run_id>/`. `NIGHTSHIFT_RUN_ID`/`NIGHTSHIFT_RUN_DIR`
propagate through the environment to role dispatch (`nightshift-agent.sh`) and retry
accounting (`nightshift-retry-increment.sh`), which each append their own typed,
immutable event file under `<run_dir>/events/`. The run directory and every ancestor
are checked for symlinks and current-user ownership before anything is read from or
written to them; a failed check degrades to "metrics unavailable", never a write into
an unverified location.

**No Git means no persisted receipt.** A project with no Git repository (only ever
valid with `--branch none`) has nowhere private and race-free to persist a run to,
so `init` reports `metrics_available: false` and every later summary call is a no-op
beyond printing to stdout; there is no best-effort fallback write into the project
tree.

At the end of the run, `nightshift-factory.sh summary`-izes the run into
`<run_dir>/summary.json`, written atomically (temp file + rename) so a concurrent
reader only ever sees a complete file:

```json
{
  "schema_version": 1,
  "run_id": "…",
  "elapsed_seconds": 42.7,
  "terminal_status": "provider_exited_0",
  "preflight_reason": null,
  "observations": [
    {"invocation_id": "…", "stage": "implement", "provider": "claude", "model": "sonnet",
     "role": "nightshift-engineer", "duration_seconds": 12.5, "status": "success",
     "usage": {"input_tokens": 1000, "output_tokens": 300}}
  ],
  "repair_count": 1,
  "usage": {"input_tokens": 1000, "output_tokens": 300, "complete": true}
}
```

`terminal_status` is one of `running`, `preflight_blocked`, `provider_exited_0`,
`provider_exited_nonzero`, `interrupted`. **A `provider_exited_0` terminal status is
not itself proof of a verified, delivered result** — it only records that the provider
process ran and returned control; downstream gates (independent review, drift, tests)
are the actual verification, unchanged by any of this.

`repair_count` sums the run-linked deltas `nightshift-retry-increment.sh` emits after
each *persisted* counter increment (never a duplicate, never a raw historical
absolute count). No repair events means unknown, not proof of zero repairs.
Observed deltas describe recorded repairs; missing instrumentation cannot prove
complete coverage. A missing or unavailable metrics context (no Git, ownership/symlink
rejection) reports `repair_count: null` — unknown, never assumed zero. This does not
read, alter, or duplicate the existing per-issue adversarial repair budget policy.

`usage` aggregates only `input_tokens`/`output_tokens` actually present in a provider's
own structured envelope: today that means Claude's raw JSON `usage` object, inspected
before the dispatcher's `.structured_output`/`.result` projection discards it. Codex's
`--json` event stream has no documented structured token-usage event observed at this
provider boundary yet, so Codex/local usage stays `null` rather than guessed.
`usage.complete` is `false` whenever any recorded observation is missing a token
count, so a partial sum is never mistaken for a complete one.

### Dispatcher observations

Each `nightshift-agent.sh` invocation appends one observation event on exit (success,
failure, or interrupt), independent of and in addition to its existing per-dispatch
lifecycle telemetry file (`role/provider/model/gear/started_at/finished_at/status/pid`
under `.nightshift/agents/`, unchanged and still backward compatible). The role→stage
map is fixed and trusted, never inferred from model output: `nightshift-engineer` and
`nightshift-architect` → `implement`; `nightshift-spec-writer` → `product`.
`nightshift-code-fact-extractor` and `nightshift-run-all-tests` are used from more than
one pipeline stage, so their stage is `null` unless the caller supplies a validated
`--stage` (one of `product`, `adversarial`, `implement`, `review`, `drift`,
`preflight`, `deploy`) — an unrecognized supplied stage is dropped to `null`, never
guessed. The recorded `model` is always the dispatcher's own routed/selected value
(the same provenance `nightshift-agent.sh` already stamps into `artifacts.model`),
never a model's self-report; an empty factory `MODEL` records as `null`.

### What is never captured

No prompts, transcripts, ticket titles/bodies, file paths, full shell commands,
environment dumps, stdout/stderr, or credential/header/cookie values are ever accepted
as metrics content — only the allowlisted typed fields above. Every string field is
additionally scrubbed against the current process's own known-credential environment
values (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CODEX_API_KEY`,
`JIRA_TOKEN`, `MONDAY_TOKEN`, `NOTION_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`) as defense in
depth. That scrub is provenance-based (a known secret's actual value), not a claim
that no string field can ever carry a secret, and it is not skipped because a given
run's configuration might be hostile — the same fixed logic runs every time. Numeric
fields are bounded to non-negative integers; `elapsed_seconds` is always finite;
timestamps are parsed UTC; string fields have field-specific length bounds. Unknown
properties are dropped by construction — the CLI only accepts the named, validated
flags documented above, and a symlinked or non-owned run context is rejected outright
rather than read from or written to.

### Metrics failures are non-fatal

Every metrics I/O or validation failure is a fixed warning on stderr
(`nightshift-run-metrics: warning: …`); the script that raised it still exits 0 and the
run it describes is never blocked, retried, or altered because metrics could not be
recorded.

## Limitations

- Query-style batch inputs (a JQL string, a saved search, anything that is not an
  explicit `REF[,REF...]` list) are not expanded by the preflight check — it reports
  `INPUT_RESOLUTION_REQUIRED` and asks for an explicit list, since expansion is itself
  a live network operation reserved for the actual run.
- Token usage is `null` for every provider/model combination that does not expose a
  documented structured usage field at the dispatcher's current provider boundary
  (today, that is Codex and local/Ollama).
- No Git repository means no persisted run receipt; `--branch none` in a non-Git
  project is otherwise fully supported.
- A hard process kill (`SIGKILL`) cannot run any exit trap, so no `interrupted`
  summary is written for that case — the run directory's `context.json` (and any
  events already flushed) is still on disk for manual inspection.
- Metrics I/O errors (permissions, disk full, a rejected symlinked/non-owned context)
  degrade to the fixed warnings described above; they are never retried automatically
  and never surface as a run failure by themselves.

## Works Cited

- `scripts/nightshift-factory.sh` — existing baseline/manifest/auth-probe/provider
  sequencing this feature slots into.
- `scripts/nightshift-worktree.sh` — existing `prepare`/`finish` predicates the new
  `check` operation reuses.
- `scripts/nightshift-ticket-source.sh` — existing per-source ticket classification
  the new `--derive-id` mode reuses.
- `scripts/nightshift-agent.sh` — existing dispatcher envelope handling and
  per-dispatch lifecycle telemetry this feature adds observations alongside.
- `scripts/nightshift-retry-increment.sh` — existing retry counter this feature
  emits a linked delta event from.
- `docs/NIGHTSHIFT-COST-POLICY.md` — "missing usage or cost information means
  unknown, not zero"; this feature's `repair_count`/`usage` nulls follow that policy.

## Follow-ons (not implemented here)

This ticket is scoped to preflight admission and run metrics only. The efficiency
roadmap items below are follow-on work, tracked separately, and nothing here asserts
they are done:

- [#9 Bounded handoffs](https://github.com/doctor-ew/nightshift-community/issues/9)
- [#10 Evidence cache](https://github.com/doctor-ew/nightshift-community/issues/10)
- [#11 Targeted repairs](https://github.com/doctor-ew/nightshift-community/issues/11)
- [#12 Measured gearshifting](https://github.com/doctor-ew/nightshift-community/issues/12)
- [#13 Pre-build behavioral proof](https://github.com/doctor-ew/nightshift-community/issues/13)
- [#14 Optional MEX spike](https://github.com/doctor-ew/nightshift-community/issues/14)
- [#18 Provider-neutral core](https://github.com/doctor-ew/nightshift-community/issues/18)
- [#19 Regression guard](https://github.com/doctor-ew/nightshift-community/issues/19)
- [#20](https://github.com/doctor-ew/nightshift-community/issues/20) (see
  `docs/EFFICIENCY-ROADMAP.md` for sequencing)

See `docs/EFFICIENCY-ROADMAP.md` for how this ticket's output feeds those.
