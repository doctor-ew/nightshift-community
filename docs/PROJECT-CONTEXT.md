# Project context and conventions

Use `scripts/nightshift-project-context.py` for project identity and applicable
convention discovery. It reads files and returns JSON; it never executes commands,
writes state, contacts providers, or interprets prose as trusted shell code.

## Project identity

Explicit `--project DIR` takes precedence. Otherwise, `NIGHTSHIFT_PROJECT_DIR`
is the neutral runtime context; `CLAUDE_PROJECT_DIR` is a legacy ingress fallback.
If both identify different physical directories, discovery blocks. Equivalent
symlink paths are not a conflict. With neither variable set, use Git root, then
current directory. `--cwd-default` preserves current-directory fallback for hooks.
The launcher preserves its existing explicit-project/current-directory behavior.

`--root-only` prints only the physical root. `--shell` emits a shell-quoted export
of the neutral variable and clears the legacy variable. Both modes resolve only
identity. Capture successful shell output before evaluating it; never evaluate
JSON or project content. Entering a ticket worktree and returning to a controller
both require an explicit project switch through this interface. Batch ledger
operations retain the controller root while ticket edits use the ticket root.

## Convention decision

Full discovery optionally accepts `--scope DIR`, relative to the project or
absolute within it. It returns existing `AGENTS.md` and legacy `CLAUDE.md` paths
along the root-to-scope ancestor chain, in that order at each level. Sibling
instructions are excluded. Unreadable or escaping convention paths block.
Runtime-level instructions outside the repository remain applicable as supplied
by that runtime; this helper does not recursively search user homes.

Before selecting any test or deployment command, the active runtime must:

1. Read all returned applicable instructions. Apply scoped `AGENTS.md` guidance;
   use legacy `CLAUDE.md` guidance only where neutral instructions are silent.
2. Compare all explicit commands, including optional configured test commands.
   If explicit applicable commands disagree, report a conflict and stop before
   execution. Do not choose one silently, combine flags, or infer that configuration
   overrides an instruction. A more specific instruction may explicitly supersede
   an ancestor; record that instruction and source when it resolves the conflict.
3. Record the selected exact command, source path and line, scope, and legacy
   fallback or explicit supersession rationale in the stage receipt. Discovery's
   `convention_policy: runtime_review_required` is not execution approval.
4. Only when all instructions and configuration are silent, use the existing
   test-role lockfile/manifest heuristics. Multiple conflicting signals block.
   Preserve the package manager, runner, and every explicit flag.

`.nightshift.toml` takes precedence over `nightshift.toml`. Full discovery parses
TOML and returns optional `[tests].command` without executing it. The tests value
must be a table; command must be a nonblank string with no line break or NUL.
Malformed/unreadable canonical configuration blocks without legacy fallback.
Absent manifests are allowed for discovery; factory admission still requires its
existing manifest contract. JSON includes the command and manifest source path.
Prose agreement is evaluated by the runtime, not a regular-expression parser.

Deployment target lookup keeps canonical deploy JSON, then legacy deploy JSON,
then resolved conventions, then existing heuristics. Production authorization
remains a separate required decision.

## Optional document capability

Adapters discover actual available tool names and provide two JSON files:
`--mapping` contains the `document-read` operation mapped to an exact tool name;
`--available-tools` contains an array of exact available names. Names must match
`[A-Za-z_][A-Za-z0-9_]*`. Invoke the existing capability helper with
`--resolve document-read --mapping FILE --available-tools FILE`.

An exact available match returns JSON with `status: available` and `tool`, exit 0.
Missing optional inputs or an unavailable tool return `status: unavailable`, exit 1.
Malformed mapping/inventory or an unknown operation fails, exit 64. This branch
performs no CLI probes, cache writes, network calls, authentication or execution.
The mapping conveys availability, not permission. The runtime must verify the
selected tool's actual schema before invoking it. Missing capability or a failed
optional document fetch retains the product stage's warning and empty context.
Provider-specific names belong in adapter-supplied mappings, not core instructions.
