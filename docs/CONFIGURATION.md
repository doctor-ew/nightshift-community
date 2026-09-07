# Configuration

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
