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
