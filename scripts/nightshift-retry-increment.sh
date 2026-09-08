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
bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" "$KEY" "$NEW" || exit $?
# Emit the run-linked delta only now that the increment is durably persisted.
# This is a substantive repair count (a retry the caller actually took),
# distinct from infrastructure-only dispatch attempts that never reach here;
# it does not read, alter, or duplicate any adversarial repair budget policy.
if [ -n "${NIGHTSHIFT_RUN_DIR:-}" ] && command -v python3 >/dev/null 2>&1; then
  python3 "${SCRIPT_DIR}/nightshift-run-metrics.py" event --run-dir "$NIGHTSHIFT_RUN_DIR" --kind repair \
    --task "$TASK" --key "$KEY" --old "$CUR" --new "$NEW" >/dev/null 2>&1 || true
fi
echo "RETRY_INCREMENT: ${KEY} ${CUR} → ${NEW}"
echo "$NEW"
