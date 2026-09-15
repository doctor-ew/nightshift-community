# Configuration

Interactive setup asks the ticket source and model/runtime first. The launcher
infers an explicit source such as spec: or gh: instead of asking again. The runtime
choice accepts codex, claude, ollama or local, optionally followed by :model.
Explicit launcher runtime/model flags are carried into setup.

Then choose defaults or customize. Defaults fill only missing fields: existing
settings are preserved, repair budgets default to three, confirmation policies
stay enabled, and the production URL remains an unconfigured placeholder.
Customization exposes the remaining missing settings individually. Unattended
incomplete configuration still fails rather than assuming consent to defaults.

Run `nightshift setup --project DIR` in an interactive terminal to fill missing
fields. Installation can invoke the same wizard with `--setup-project DIR`.
Canonical configuration is `.nightshift.toml`; existing `nightshift.toml` remains
read-compatible. Setup copies legacy content without deleting or changing it.
Existing canonical changes retain uniquely named private `.setup-backup-*` files;
atomic publication prevents exposing partially written configuration. Unattended incomplete runs emit JSON with missing
field names and exit without prompting. Invalid TOML is never silently repaired.

Precedence: command flags, project configuration, shared runtime configuration,
built-in defaults. `[runtime]` accepts `provider` (`codex`, `claude`, `ollama` or
`local`) and `model`. Omitted provider means Codex. Authentication remains
subscription by default; saved API settings cannot opt a run into billing.
Only explicit `--auth api` authorizes the existing API runtime path.

`[providers].routing_file` drives the shared role dispatcher; `[routing].file`
is an optional explicit override in the same configuration layer. Project paths
resolve from the project, global paths from the runtime home.
`[routing].local_model` selects its local model.
`--gear` and `--risk` select its run preferences; mandatory gates are unchanged.
Setup requires Python 3.11+ (`tomllib`). Existing production URL placeholders are
not live deployment destinations and must be configured before deployment.

Optional `[tests].command` declares an exact test command. It must be a nonblank
single-line string. Configuration does not silently override applicable project
instructions: conflicting explicit commands block before execution. See
[Project context and conventions](PROJECT-CONTEXT.md) for scoped AGENTS.md guidance,
legacy CLAUDE.md fallback, provenance, and neutral runtime context.

## Behavioral proof

Optional `[behavior_proof]` uses safe helper defaults when absent; setup need not
materialize the section. Canonical manifest precedence is unchanged. Validate it
through normal manifest validation or `nightshift-behavior-proof.py validate
--project DIR --config-only`.

| Key | Default | Accepted values |
| --- | --- | --- |
| version | 1 | 1 |
| development_calls | 8 | Integer 1..64 |
| final_calls | 2 | Integer 1..64 |
| repairs | 2 | Integer 0..2 |
| infrastructure_failures | 2 | Integer 0..2 |
| timeout_seconds | 120 | Integer 1..120 |
| output_bytes | 1048576 | Integer 1..1048576 |
| force_prompt | false | Boolean; strengthens required prototype coverage only |

Unknown keys, booleans used as integers, malformed tables and unsupported versions
are invalid. Lower budgets block earlier; they never waive required proof. With
zero infrastructure retries, the initial successful attempt is permitted but the
first infrastructure failure blocks retries. Effective policy is pinned to the
canonical task ledger; changing a config or report path does not reset it.
`force_prompt` retains deterministic tests and adds reviewed prototype coverage;
an unsupported intended runtime blocks. It cannot turn required agent/runtime
behavior into a documentation-only exemption. The proof profile is subscription
only regardless of other explicitly authorized runtime authentication paths.

See [Behavioral proof](BEHAVIOR-PROOF.md) for scenarios, admission, evidence,
private final cases and supported runtime limits.

## Claude-only provider policy

For a project restricted to Claude, add `policy` to the existing providers table
in `.nightshift.toml` (do not duplicate the table):

```toml
[providers]
policy = "claude-only"
routing_file = "routing.json"
```

The default policy is `standard`. For one run:

```bash
nightshift jira:IF-301 --provider-policy claude-only --branch auto --push --pr
```

Claude-only selects Claude for the orchestrator and every managed role, including
low-risk extraction that would otherwise select a local model. It uses a configured
Claude route for each role; if no such route exists, it fails before provider launch.
An explicit Codex/local orchestrator selection is rejected. Existing subscription
and per-run API authentication rules still apply.

A restriction in the project, primary checkout, global configuration, or inherited
`NIGHTSHIFT_PROVIDER_POLICY` cannot be relaxed by a child or a `standard` override.
Direct role invocations and worktrees resolve the policy as well. The factory
propagates the effective policy to its workers. Invalid policy values fail closed.

Reviews remain separate Claude invocations with no author-session resume and no
session persistence. Receipts record `provider_policy:claude-only` and
`review_independence:fresh-session`; behavioral challenge receipts also bind the
policy to the approval. Tests, scope, author identity, evidence digests and bounded
repair gates are unchanged. This policy provides session independence, not
cross-provider diversity. It does not implement Azure AI Foundry.

This is enforcement at Nightshift's managed provider launch boundaries, not an
OS/network sandbox for arbitrary model-generated shell commands or independently
started tools. Use workplace endpoint controls where an organization requires
machine-wide provider restrictions.

## Factory worktree base and role reporting

New ticket worktrees use the branch referenced by `refs/remotes/origin/HEAD`,
refreshed from the remote before creation. They do not inherit a prototype
checkout merely because the command was started there. Repositories without
remotes use `HEAD`. If a remote exists but its default branch is unknown,
preparation stops with a request for an explicit base.

Use `nightshift <ticket-ref> --base <ref>` to select a prerequisite branch or
another verified base. Existing owned worktrees retain their recorded base;
Nightshift does not reset them when the remote advances.

The launcher consumes `--branch`, `--push`, and `--pr` and supplies publication
policy separately from the engineering stage arguments. A factory run never
invokes the deployment stage or merges its PR.

Claude factory workers disable native `Agent` and `Task` tools. All role calls
must use `scripts/nightshift-agent.sh` for provider policy, contract validation,
and dashboard lifecycle reporting. The factory itself also appears in Agents
while preparing the first stage.
