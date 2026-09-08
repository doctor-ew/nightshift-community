# Branding and provider-coupling audit

The scoped audit checks maintained source and explicitly selected installed
Nightshift artifacts. It is a static regression guard with a finite rule set.
It does not certify arbitrary prose, repository history, or other applications.

## Invocation

Run the source audit from a checkout:

```sh
python3 scripts/nightshift-branding.py --project . --inventory source
```

`--inventory` accepts `source`, `installed`, and `all`; the default is `source`.
Installed requests require all four explicit destination arguments: `--target`,
`--codex-target`, `--nightshift-target`, and `--bin-target`. `--runtime` accepts
`claude`, `codex`, `local`, or `all` and defaults to `all`. Local uses the Codex
skill mapping. The selected project is an explicit source checkout; Git metadata
is unnecessary. The installed scanner imports the adjacent inventory helper
without writing Python bytecode.

`install.sh --check` supplies its resolved destinations and requests both
inventories. It exits before dependency probes, installation, repair, hook reads,
directory creation, migration, or update configuration. A fresh target returns
non-success because the requested installed inventory is unavailable.

## Source boundary

The maintained root files are `README.md`, `CLAUDE.md`, `AGENTS.md`, `SECURITY.md`,
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `VERSION`, `.gitignore`,
`install.sh`, `routing.json`, and `nightshift.toml`. The audit includes descendants
of `scripts/`, `commands/`, `agents/`, `skills/`, `tests/`, `docs/`, `contracts/`,
`evals/`, `dashboard/`, and `.github/`. This includes retained task documents,
test fixture declarations, and generated dashboard distribution text.

Excluded artifacts are `dashboard/node_modules/`, directories named
`__pycache__`, and files ending in `.pyc` or `.pyo`. Exclusions are reported when
encountered. An absent optional `dashboard/dist` is reported as `not_installed`.
Missing required files or roots, unsupported objects, unreadable directories,
invalid UTF-8, and oversized artifacts produce incomplete coverage. The audit
does not open `.git`, local `.nightshift.toml`, runtime state, credentials, or
unrelated user homes. Source links must remain within the physical project;
links are checked before traversal, and cycles are rejected.
Resolution preserves component order across parent-directory steps. A link
cannot use a directory or another link followed by `..` to make a different
physical target appear to match the declared source.

## Installed ownership

`scripts/nightshift-install-inventory.py` owns the shared installation mappings.
Both installer operations and the audit consume `make_inventory`. The scanner
does not derive destinations from ownership records or maintain an independent
mapping list.

`install-links.json` is a destination-to-source object. The scanner rejects
duplicate keys, malformed records, unknown destinations, and source mismatches
before using any record. A valid tree-root record covers only corresponding
source descendants. Unknown siblings, user settings, hooks, and backup trees
are outside the installed inventory. An unknown copy is reported without reading
its contents. A mapped symlink can independently establish ownership only when
it points to its exact declared source. Missing records remain visible as
informational `missing_ownership` coverage when a valid symlink permits scanning;
they do not fail the audit by themselves. Unknown regular copies still fail.

Configured roots are explicitly canonicalized. Links below a configured root
must correspond to the mapped source. Ancestor escapes, nested escapes, dangling
links, missing files, and unknown ownership each prevent complete coverage.
The audit reads mapped configuration files as text; it does not follow resource
references or execute their contents.

## Rules and exceptions

The rule identifiers are:

| Rule | Detection boundary |
| --- | --- |
| `retired-brand` | Case-insensitive filename and content matches for `"cx" + "eng"`, `"con" + "nexure"`, `"drew" + r"[-_ ]pipeline"`, `"drew" + "-"`, the slash family `"/" + "cx"` with command boundaries and hyphenated suffixes, and `"CX" + " ADR-002"`. |
| `provider-mcp` | Explicit double-underscore MCP tool names and single-underscore MCP names containing the supported provider identifiers. |
| `provider-executor` | Direct Claude print commands, Codex execution commands, affirmative run/invoke/execute/use directives, and passive run/executed/performed-by directives naming those executors, with optional inline execution. |
| `role-model` | Actual `model:` keys in the opening role frontmatter, excluding comments. |
| `legacy-project-context` | Legacy project-variable references in canonical command, role, and script content. |
| `legacy-convention` | Legacy convention-file references in canonical command, role, and script content. |

Provider rules apply to Markdown under `commands/` and `agents/` and shell or
Python files under `scripts/`. Comment lines and explicit negative execution
directives are distinguished from affirmative executor calls. These patterns
do not interpret arbitrary natural-language instructions. The letters CX alone
are not prohibited.

`scripts/nightshift-branding-policy.json` has exactly `version` and `exceptions`
at the root. Version is integer `1`. Each exception has exactly `rule`, `path`,
`context`, and `reason`. The path is an exact repository-relative path; context
is an exact source line, or the exact relative path for a filename finding.
The rationale must be nonblank. Unknown keys, unsupported rules, invalid types,
duplicate exceptions, and unused exceptions invalidate the policy.

Exceptions preserve the shared project resolver, reviewed compatibility
boundaries, convention reconciliation instructions, and existing provider
dispatch/authentication contexts. They do not exempt a whole provider, script,
or directory. Installed matches use their validated source-relative mapping and
exact current line. Altering an excepted installed line removes that exemption.
The source inventory is read to validate exception usage for installed-only
requests as well; source findings are reported only when source was requested.

## JSON and exit status

Every invocation returns JSON with `status`, `inventories`, `findings`, and
`coverage`. Normal status is `pass` or `fail`; invalid arguments or policy use
`invalid`. Inventory records contain `status` and counts for `discovered`,
`scanned`, `missing`, `unreadable`, `unknown`, and `excluded`.

Findings contain `inventory`, `rule`, logical relative `path`, and `line`.
Filename findings use line `0`. Coverage records contain `inventory`, logical
relative `path`, and a fixed `reason`. Output never includes matching text,
exception contexts, absolute user paths, link targets, or exception messages.
Control characters in filenames are JSON-escaped. Results are sorted for
deterministic comparison.

| Exit | Meaning |
| --- | --- |
| `0` | Requested coverage is complete and no findings remain. |
| `1` | Findings or incomplete/unavailable coverage. |
| `64` | Invalid arguments or policy. |

Artifact reads are bounded at 4 MiB. Ownership records and policy are bounded at
1 MiB. A larger artifact or ownership file produces coverage failure; a larger
policy is invalid. Reads enforce limits on actual bytes, including when file
size metadata changes. The audit writes no files and starts no provider or
dependency commands.
