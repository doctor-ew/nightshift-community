#!/usr/bin/env bash
# nightshift-scope-freeze.sh — PreToolUse hook for Edit/Write that blocks edits outside
# the union of all active per-ticket scope freezes.
#
# Activation:
#   Hook is a no-op unless at least one .active-scope-<TICKET> file exists in
#   a resolved task state directory. nightshift-scope-activate.sh creates these;
#   matching worktree finish retires the ticket's lease and scope on completion.
#
# .active-scope-<TICKET> file format:
#   First line: ticket key (informational)
#   Subsequent lines: one repo-relative file path per line. Glob patterns OK.
#
# Union semantics: an edit is ALLOWED if it matches ANY active scope.
#   An edit is BLOCKED only if it matches NONE of the active scopes.
#
# Hook input (stdin, JSON from Claude Code):
#   { "tool_name": "Edit"|"Write", "tool_input": { "file_path": "/abs/path" }, ... }
#
# Decision contract (stdout JSON):
#   { "decision": "approve" }
#   { "decision": "block", "reason": "..." }
#
# Exit code 0 always.

set -euo pipefail

INPUT=$(cat)

PROJECT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCOPE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT")

# Collect all per-ticket scope files
SCOPE_FILES=()
if [ -d "$SCOPE_DIR" ]; then
  while IFS= read -r -d '' f; do
    SCOPE_FILES+=("$f")
  done < <(find "$SCOPE_DIR" -maxdepth 1 -name '.active-scope-*' -print0 2>/dev/null)
fi

# No active scope → approve every edit (hook is a no-op)
if [ ${#SCOPE_FILES[@]} -eq 0 ]; then
  echo '{"decision":"approve"}'
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  echo '{"decision":"approve"}'
  exit 0
fi

# Make file_path relative to project for matching
case "$FILE_PATH" in
  "$PROJECT"/*) REL="${FILE_PATH#$PROJECT/}" ;;
  *)
    # File is outside this project's directory — this project's scope freeze doesn't apply.
    echo '{"decision":"approve"}'
    exit 0
    ;;
esac

# Collect ticket IDs for the block message
BD_IDS=()
for sf in "${SCOPE_FILES[@]}"; do
  id=$(head -n 1 "$sf" 2>/dev/null || true)
  [ -n "$id" ] && BD_IDS+=("$id")
done

# Match $REL against the union of all active scope files.
# Uses python pathlib.PurePath.match for true ** support.
MATCH=$(python3 - "${SCOPE_FILES[@]}" "$REL" <<'PYEOF'
import sys, pathlib, fnmatch

args = sys.argv[1:]
if len(args) < 1:
    print("0"); sys.exit(0)

rel = args[-1]
scope_paths = args[:-1]
p = pathlib.PurePath(rel)

for scope_path in scope_paths:
    try:
        with open(scope_path) as f:
            lines = f.readlines()[1:]  # drop ticket-key header
        for line in lines:
            pat = line.strip()
            if not pat or pat.startswith("#"):
                continue
            # Exact match
            if pat == rel:
                print("1"); sys.exit(0)
            # Directory prefix (pattern ending with /)
            if pat.endswith("/") and rel.startswith(pat):
                print("1"); sys.exit(0)
            # Glob match (handles **, *, ?)
            try:
                if p.match(pat) or (hasattr(p, "full_match") and p.full_match(pat)):
                    print("1"); sys.exit(0)
            except Exception:
                pass
            # Fallback: fnmatch with ** treated as recursive
            if fnmatch.fnmatchcase(rel, pat.replace("**", "*")):
                pat_parts = pat.split("/")
                rel_parts = rel.split("/")
                if "**" in pat_parts:
                    i = pat_parts.index("**")
                    head, tail = pat_parts[:i], pat_parts[i+1:]
                    if (len(rel_parts) >= len(head) + len(tail) and
                        all(fnmatch.fnmatchcase(r, q) for r, q in zip(rel_parts[:len(head)], head)) and
                        (not tail or all(fnmatch.fnmatchcase(r, q) for r, q in zip(rel_parts[-len(tail):], tail)))):
                        print("1"); sys.exit(0)
                else:
                    print("1"); sys.exit(0)
    except Exception:
        pass

print("0")
PYEOF
)

if [ "$MATCH" = "1" ]; then
  echo '{"decision":"approve"}'
  exit 0
fi

# Block — out of scope for all active tickets
if [ ${#BD_IDS[@]} -gt 0 ]; then
  TICKETS_STR=$(IFS=", "; echo "${BD_IDS[*]}")
else
  TICKETS_STR="unknown"
fi
REASON="scope-freeze: edit to '$REL' is outside all active scopes (${TICKETS_STR}). Allowed paths are listed in ${SCOPE_DIR}/.active-scope-*. To edit outside scope, remove the relevant .active-scope-<TICKET> file."

jq -n --arg r "$REASON" '{decision:"block", reason:$r}'
exit 0
