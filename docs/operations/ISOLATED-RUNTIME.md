# Isolated runtime paths

## Implementation

Stage and role instructions resolve supporting scripts through the configured
`NIGHTSHIFT_HOME`, falling back to the existing home-directory installation when
unset or empty. Full executable paths are quoted so spaces and shell metacharacters
in an explicit runtime directory are literal path characters.

Capability caches and efficiency receipts also honor the runtime home. Explicit
`NIGHTSHIFT_CACHE_DIR` and `NIGHTSHIFT_EFFICIENCY_DIR` retain precedence. Generated
Claude hooks use the same quoted runtime-home expression. Installer migration
changes only the three exact legacy installer-generated bare hook commands;
custom, quoted, compound and unrelated commands remain intact.

## Validation

- `tests/test-runtime-home-prompts.py`: five executable sentinel tests pass,
  including configured paths with spaces/metacharacters and poisoned default
  helpers, plus unset and empty runtime-home fallback.
- `tests/test-isolated-runtime-paths-review.py`: seven tests pass, including
  actual disposable installer-generated hooks, exact legacy migration, custom
  command preservation and explicit cache/receipt precedence.
- `tests/test-pipeline.py`: six synthetic pipeline tests pass in 40.987 seconds.
  Fresh source handoff reaches actual child admission; retained controller
  budgets and decisions remain intact. No real providers are invoked.

Independent review covers both command/role paths and runtime defaults. These
checks validate configured helper routing and owned cache/receipt locations.
They do not certify live provider behavior or replace provider authentication,
user configuration or global provider hooks. No operator installation is modified
by this validation. Integrated release activation and endpoint certification remain
separate decisions.
