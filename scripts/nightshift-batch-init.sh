#!/usr/bin/env bash
set -euo pipefail
# nightshift-batch-init.sh — initialize or resume a batch state file.
#
# Usage:
#   nightshift-batch-init.sh --tickets "MVP-1,MVP-2,MVP-3" --source <jql|explicit> \
#     --source-value "<string>" [--batch-n N] [--resume <filename>]
#
# Fresh start: writes .claude/task-progress/batch-YYYYMMDD-HHMM.json
#   Prints: BATCH_STATE_PATH: .claude/task-progress/batch-YYYYMMDD-HHMM.json
#           BATCH_TICKET: MVP-1   (one per ticket, in order)
#
# --resume <filename>: reads .claude/task-progress/<filename>, validates structure
#   Prints: BATCH_STATE_PATH, RESUME_FROM (first non-complete/non-skipped key), BATCH_TICKET lines.
#
# Exits 0 on success, 1 on error.

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
PROJECT="$(cd "$PROJECT" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TICKETS=""
SOURCE=""
SOURCE_VALUE=""
BATCH_N="5"
RESUME_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --tickets)      TICKETS="$2"; shift 2 ;;
    --source)       SOURCE="$2"; shift 2 ;;
    --source-value) SOURCE_VALUE="$2"; shift 2 ;;
    --batch-n)      BATCH_N="$2"; shift 2 ;;
    --resume)       RESUME_FILE="$2"; shift 2 ;;
    *)              shift ;;
  esac
done

if [ -n "$RESUME_FILE" ]; then
  STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$(basename "$RESUME_FILE")")
else
  STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --create)
fi

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required but not installed" >&2; exit 1; }

# Resume path
if [ -n "$RESUME_FILE" ]; then
  BASENAME=$(basename "$RESUME_FILE")
  if ! echo "$BASENAME" | grep -qE '^batch-[0-9]+-[0-9]+\.json$'; then
    echo "ERROR: invalid resume filename '$RESUME_FILE' — expected batch-YYYYMMDD-HHMM.json" >&2
    exit 1
  fi
  STATE_PATH="${STATE_DIR}/${BASENAME}"
  [ ! -f "$STATE_PATH" ] && { echo "ERROR: resume file not found: $STATE_PATH" >&2; exit 1; }
  jq -e . "$STATE_PATH" >/dev/null 2>&1 || { echo "ERROR: malformed JSON in resume file: $STATE_PATH" >&2; exit 1; }

  echo "BATCH_STATE_PATH: ${STATE_PATH#$PROJECT/}"
  RESUME_FROM=$(jq -r '
    .tickets[] as $k |
    if (.statuses[$k].status // "pending") | test("^(complete|skipped)$") | not
    then $k else empty end
  ' "$STATE_PATH" 2>/dev/null | head -1)
  [ -n "$RESUME_FROM" ] && echo "RESUME_FROM: $RESUME_FROM"
  jq -r '.tickets[]' "$STATE_PATH" | while read -r KEY; do
    echo "BATCH_TICKET: $KEY"
  done
  exit 0
fi

# Fresh start
[ -z "$TICKETS" ] && { echo "ERROR: --tickets required for fresh batch start" >&2; exit 1; }
[ -z "$SOURCE" ]  && { echo "ERROR: --source required" >&2; exit 1; }

TIMESTAMP=$(date -u +"%Y%m%d-%H%M")
STATE_FILE="batch-${TIMESTAMP}.json"
STATE_PATH="${STATE_DIR}/${STATE_FILE}"
CREATED=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

IFS=',' read -ra RAW_ARRAY <<< "$TICKETS"
TICKET_ARRAY=()
for t in "${RAW_ARRAY[@]}"; do
  trimmed="${t#"${t%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  [ -n "$trimmed" ] && TICKET_ARRAY+=("$trimmed")
done
[ "${#TICKET_ARRAY[@]}" -eq 0 ] && { echo "ERROR: --tickets resolved to empty list after parsing" >&2; exit 1; }

TICKETS_JSON=$(printf '%s\n' "${TICKET_ARRAY[@]}" | jq -R . | jq -s .)
STATUSES_JSON=$(printf '%s\n' "${TICKET_ARRAY[@]}" | jq -R . | jq -s 'reduce .[] as $k ({}; .[$k] = {"status": "pending"})')
SKIP_REASONS_JSON=$(printf '%s\n' "${TICKET_ARRAY[@]}" | jq -R . | jq -s 'reduce .[] as $k ({}; .[$k] = null)')
TOTAL="${#TICKET_ARRAY[@]}"

jq -n \
  --arg batch_id "$TIMESTAMP" \
  --arg created "$CREATED" \
  --arg source "$SOURCE" \
  --arg source_value "$SOURCE_VALUE" \
  --argjson batch_n "$BATCH_N" \
  --argjson tickets "$TICKETS_JSON" \
  --argjson statuses "$STATUSES_JSON" \
  --argjson skip_reasons "$SKIP_REASONS_JSON" \
  --argjson total "$TOTAL" \
  '{
    batch_id: $batch_id, created: $created, source: $source, source_value: $source_value,
    batch_n: $batch_n, tickets: $tickets, current: null,
    statuses: $statuses, skip_reasons: $skip_reasons,
    metrics: { complete: 0, skipped: 0, failed: 0, pending: $total }
  }' > "$STATE_PATH"

echo "BATCH_STATE_PATH: ${STATE_PATH#$PROJECT/}"
for KEY in "${TICKET_ARRAY[@]}"; do
  echo "BATCH_TICKET: $KEY"
done
