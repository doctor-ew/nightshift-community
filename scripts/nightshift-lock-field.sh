#!/usr/bin/env bash
# nightshift-lock-field.sh — read/write fields in the per-task lock sidecar.
#
# nightshift's tracker is a human-facing markdown file. TDD lock SHAs and retry
# counters are machine state, so they live in a separate key=value sidecar at
# .claude/task-progress/<task-key>.locks — decoupled from the markdown format.
#
# Usage:
#   nightshift-lock-field.sh <task-key> <KEY> <VALUE>   # set KEY=VALUE (replace if present, else append)
#   nightshift-lock-field.sh <task-key> --get <KEY>     # print current value of KEY (empty if unset)
#   nightshift-lock-field.sh <task-key> --cat           # print the whole sidecar
#
# Idempotent setter: a repeated key is replaced in place, never duplicated.
set -uo pipefail

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK="${1:-}"
ARG2="${2:-}"

[ -z "$TASK" ] && { echo "ERROR: task-key required" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$TASK" --create)
LOCKS="${STATE_DIR}/${TASK}.locks"

if [ "$ARG2" = "--cat" ]; then
  [ -f "$LOCKS" ] && cat "$LOCKS" || true
  exit 0
fi

if [ "$ARG2" = "--get" ]; then
  KEY="${3:-}"
  [ -z "$KEY" ] && { echo "ERROR: --get requires a KEY" >&2; exit 1; }
  [ -f "$LOCKS" ] && grep "^${KEY}=" "$LOCKS" 2>/dev/null | tail -1 | cut -d= -f2- || true
  exit 0
fi

KEY="$ARG2"
VALUE="${3:-}"
[ -z "$KEY" ] && { echo "ERROR: KEY required" >&2; exit 1; }

touch "$LOCKS"
if grep -q "^${KEY}=" "$LOCKS" 2>/dev/null; then
  # Replace in place (bash 3.x / BSD sed safe — write to temp then move)
  TMP="$(mktemp)"
  grep -v "^${KEY}=" "$LOCKS" > "$TMP" || true
  echo "${KEY}=${VALUE}" >> "$TMP"
  mv "$TMP" "$LOCKS"
else
  echo "${KEY}=${VALUE}" >> "$LOCKS"
fi
