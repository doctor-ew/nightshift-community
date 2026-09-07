#!/usr/bin/env bash
# nightshift-scope-thaw.sh — deactivate a per-ticket scope-freeze by removing its
# .active-scope-<TASK_KEY> file.
#
# nightshift-scope-freeze.sh enforces the union of all .active-scope-* files in
# .claude/task-progress/. /nightshift-implement removes its file on success and
# /nightshift-eng's trap removes it on a clean exit — but a crashed or killed session
# leaves the file behind, which then blocks ALL edits everywhere (the global
# hook is union-of-active, and an orphaned scope is still "active"). Run this to
# clear one ticket's scope explicitly. See nightshift-crash-check.sh for detection.
#
# Usage: nightshift-scope-thaw.sh <task-key>
#   Falls back to NIGHTSHIFT_TICKET from the ACTIVE-* file if no arg is given.
PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK=$(echo "${1:-$ARGUMENTS}" | sed -E 's/--[a-z]+( [a-z-]+)?//g' | xargs)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT")
[ -z "$TASK" ] && TASK=$(grep -h "^NIGHTSHIFT_TICKET=" "${STATE_DIR}/ACTIVE-"* 2>/dev/null | head -1 | cut -d= -f2)
[ -z "$TASK" ] && { echo "ERROR: could not resolve task-key — scope-freeze NOT deactivated." >&2; exit 1; }

STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$TASK")
SCOPE="${STATE_DIR}/.active-scope-${TASK}"
if [ -f "$SCOPE" ]; then
  rm -f "$SCOPE"
  echo "SCOPE_THAWED: ${TASK} (removed ${SCOPE#$PROJECT/})"
else
  echo "SCOPE_NOT_FOUND: no active scope for ${TASK}"
fi
