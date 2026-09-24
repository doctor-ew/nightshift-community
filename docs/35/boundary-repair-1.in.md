# Bounded runtime syntax and exit-preservation repair
Plan approved; read-only proposal only for scripts/nightshift-factory.sh. No tests, test logs, proof or other reports. Return applicable artifacts.diff; controller integrates and validates. No nested workers/file writes.

Public contract violation: the new Claude launch uses parameter expansion to conditionally insert a shell redirection; shell grammar cannot create a redirection operator through parameter expansion. Replace this with explicit valid shell branching or a safe launch helper. Capture stdout without altering provider exit status. Preserve existing authentication and signal behavior. Read only relevant source. This is a small repair; no plan approval stop needed.
