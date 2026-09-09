#!/usr/bin/env bash
set -euo pipefail
# nightshift-batch-retro.sh — write an aggregate retro from the batch state JSON.
#
# Usage: nightshift-batch-retro.sh --state <repo-relative-path>
#
# Reads the batch state, writes .claude/task-progress/batch-YYYYMMDD-HHMM-retro.md,
# commits it (non-blocking), and prints: BATCH_RETRO: <path>.
# Local-only: no telemetry, no external emit — just a markdown summary of what ran.
# Exits 0 on success, 1 on error.

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --state) STATE="$2"; shift 2 ;;
    *)       shift ;;
  esac
done

[ -z "$STATE" ] && { echo "ERROR: --state required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required but not installed" >&2; exit 1; }

STATE_PATH="${PROJECT}/${STATE}"
[ ! -f "$STATE_PATH" ] && { echo "ERROR: state file not found: $STATE_PATH" >&2; exit 1; }

BATCH_ID=$(jq -r '.batch_id' "$STATE_PATH")
STATE_DIR=$(dirname "$STATE")
[ "$STATE_DIR" = "." ] && STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --create | sed "s|^${PROJECT}/||")
CREATED=$(jq -r '.created' "$STATE_PATH")
COMPLETED=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SOURCE=$(jq -r '.source' "$STATE_PATH")
SOURCE_VALUE=$(jq -r '.source_value' "$STATE_PATH")
TOTAL=$(jq '.tickets | length' "$STATE_PATH")
COMPLETE=$(jq '.metrics.complete' "$STATE_PATH")
SKIPPED=$(jq '.metrics.skipped' "$STATE_PATH")
FAILED=$(jq '.metrics.failed' "$STATE_PATH")
BLOCKED=$(jq '.metrics.blocked // 0' "$STATE_PATH")
NEEDS_DECISION=$(jq '.metrics["needs-decision"] // 0' "$STATE_PATH")
PENDING=$(jq '.metrics.pending' "$STATE_PATH")

if [[ "$TOTAL" =~ ^[0-9]+$ ]] && [[ "$COMPLETE" =~ ^[0-9]+$ ]] && [ "$TOTAL" -gt 0 ]; then
  PCT=$(echo "scale=0; $COMPLETE * 100 / $TOTAL" | bc 2>/dev/null || echo "?")
  COMPLETION_RATE="${COMPLETE}/${TOTAL} (${PCT}%)"
else
  COMPLETION_RATE="0/0"
fi

SKIP_REASONS=$(jq -r '
  [.skip_reasons | to_entries[] | select(.value != null) | .value] |
  if length == 0 then "none"
  else group_by(.) | sort_by(-length) | .[0:3] | map(.[0]) | join("; ")
  end
' "$STATE_PATH")

if [ "$CREATED" != "null" ] && command -v python3 >/dev/null 2>&1; then
  WALL_MINS=$(python3 - "$CREATED" "$COMPLETED" << 'PYEOF'
import sys
from datetime import datetime
try:
    c = datetime.fromisoformat(sys.argv[1].replace('Z', '+00:00'))
    d = datetime.fromisoformat(sys.argv[2].replace('Z', '+00:00'))
    print(f'{int((d - c).total_seconds() / 60)} minutes')
except Exception:
    print('unknown')
PYEOF
) || WALL_MINS="unknown"
else
  WALL_MINS="unknown"
fi

ROWS=""
while IFS= read -r KEY; do
  STATUS=$(jq -r --arg k "$KEY" '.statuses[$k].status // "unknown"' "$STATE_PATH")
  PR_URL=$(jq -r --arg k "$KEY" '.statuses[$k].pr_url // "—"' "$STATE_PATH")
  REASON=$(jq -r --arg k "$KEY" '(.skip_reasons[$k] // .statuses[$k].reason // "—")' "$STATE_PATH")
  [ "$PR_URL" = "null" ] && PR_URL="—"
  [ "$REASON" = "null" ] && REASON="—"
  ROWS="${ROWS}| ${KEY} | ${STATUS} | ${PR_URL} | ${REASON} |
"
done < <(jq -r '.tickets[]' "$STATE_PATH")

if [ "$SOURCE" = "jql" ]; then
  SOURCE_DESC="jql — \`${SOURCE_VALUE}\`"
else
  SOURCE_DESC="explicit — \`${SOURCE_VALUE}\`"
fi

RETRO_RELATIVE="${STATE_DIR}/batch-${BATCH_ID}-retro.md"
RETRO_PATH="${PROJECT}/${RETRO_RELATIVE}"

cat > "$RETRO_PATH" << RETRO
# Batch Retro: batch-${BATCH_ID}

**Batch ID:** batch-${BATCH_ID}
**Created:** ${CREATED}
**Completed:** ${COMPLETED}
**Source:** ${SOURCE_DESC}

---

## Per-Ticket Outcomes

| Ticket | Status | PR | Skip/Fail Reason |
|--------|--------|----|------------------|
${ROWS}
---

## Aggregate

| Metric | Value |
|--------|-------|
| Tickets in batch | ${TOTAL} |
| Complete | ${COMPLETE} |
| Skipped | ${SKIPPED} |
| Failed | ${FAILED} |
| Blocked | ${BLOCKED} |
| Needs decision | ${NEEDS_DECISION} |
| Pending (incomplete) | ${PENDING} |
| Completion rate | ${COMPLETION_RATE} |
| Total wall-clock time | ${WALL_MINS} |
| Most common skip reasons | ${SKIP_REASONS} |

---

## Notes

Batch run completed. Sequential mode — one ticket at a time through /nightshift-eng.
RETRO

git -C "$PROJECT" add "$RETRO_RELATIVE" 2>/dev/null && \
  git -C "$PROJECT" commit -m "retro(batch-${BATCH_ID}): aggregate batch outcomes" 2>/dev/null || \
  echo "WARN: retro commit failed (non-blocking) — retro written to disk" >&2

echo "BATCH_RETRO: ${RETRO_RELATIVE}"
