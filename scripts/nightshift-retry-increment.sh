#!/usr/bin/env bash
set -uo pipefail
# nightshift-retry-increment.sh — increment a RETRY_* counter in the lock sidecar.
#
# Usage: nightshift-retry-increment.sh <task-key> <KEY>
#   KEY: RETRY_IMPLEMENT | RETRY_REVIEW | RETRY_DRIFT  (any RETRY_* name)
#
# Reads the current value (0 if unset), increments by 1, writes it back via
# nightshift-lock-field.sh. Prints: RETRY_INCREMENT: <KEY> <old> → <new> and echoes the
# new value on its own last line for easy capture.
# Exits 0 on success, 2 on bad args.

TASK="${1:-}"
KEY="${2:-}"
if [ -z "$TASK" ] || [ -z "$KEY" ]; then
  echo "ERROR: usage: nightshift-retry-increment.sh <task-key> <KEY>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CUR=$(bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" --get "$KEY")
[ -z "$CUR" ] && CUR=0
case "$CUR" in
  ''|*[!0-9]*) CUR=0 ;;
esac
NEW=$((CUR + 1))
bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" "$KEY" "$NEW"
echo "RETRY_INCREMENT: ${KEY} ${CUR} → ${NEW}"
echo "$NEW"
