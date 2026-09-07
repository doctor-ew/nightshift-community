# Local requirements without a hosted tracker

From your project directory, use `nightshift spec:docs/AGENT-SPEC.md --branch auto`
or `nightshift docs/AGENT-SPEC.md --branch auto`. Quote a path containing spaces.
Neither command requests a push or PR. Add --push and --pr only when wanted.
GitHub input remains `nightshift gh:NUMBER`; beads input remains `nightshift bd:ID`.
An explicit GitHub repository reference is `gh:owner/repo#NUMBER`.

The local adapter accepts UTF-8 .md/.markdown files up to 1 MiB within a registered
project worktree. It follows symlinks and rejects targets outside those worktrees.
Missing and empty files fail before product processing. The path-derived task ID
stays stable when content changes; a separate SHA-256 digest identifies content.
Renaming a source creates a different task identity.

The file is requirements input, not a pre-approved spec. The product workflow
must record the body and digest as evidence and run the same citation, adversarial,
test and review gates. No hosted issue needs to be created. A local Git repository
is still required for isolation; a selected runtime still needs its own login.
Beads remains an optional local ledger except when the input itself is a bead.

Implementation: scripts/nightshift-spec-source.py; entry routing:
commands/nightshift-eng.md; verification policy: commands/nightshift-product.md.
Release channels and update controls: [UPDATES.md](UPDATES.md).
