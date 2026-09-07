#!/usr/bin/env bash
set -euo pipefail
# nightshift-batch-update.sh — update per-ticket status in the batch state JSON.
#
# Usage:
#   nightshift-batch-update.sh --state <repo-relative-path> --ticket <KEY> \
#     --status <pending|in_progress|complete|skipped|failed|blocked|needs-decision> \
#     [--pr-url <url>] [--reason <string>] [--receipt <path>]
#
# Updates statuses.<KEY>, the current pointer, and recomputes metrics. Commits the
# state file (non-blocking — state is written to disk regardless of commit success).
# Exits 0 on success, 1 on error.

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
STATE=""; TICKET=""; STATUS=""; PR_URL=""; REASON=""; RECEIPT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --state)   STATE="$2"; shift 2 ;;
    --ticket)  TICKET="$2"; shift 2 ;;
    --status)  STATUS="$2"; shift 2 ;;
    --pr-url)  PR_URL="$2"; shift 2 ;;
    --reason)  REASON="$2"; shift 2 ;;
    --receipt) RECEIPT="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

[ -z "$STATE" ]  && { echo "ERROR: --state required" >&2; exit 1; }
[ -z "$TICKET" ] && { echo "ERROR: --ticket required" >&2; exit 1; }
[ -z "$STATUS" ] && { echo "ERROR: --status required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required but not installed" >&2; exit 1; }

# Path guard against directory traversal.
if ! [[ "$STATE" =~ ^(\.nightshift|\.drew|\.claude/task-progress)/batch-[0-9]+-[0-9]+\.json$ ]]; then
  echo "ERROR: invalid state path '$STATE' — expected .nightshift, .drew, or .claude/task-progress batch state" >&2; exit 1
fi

STATE_PATH="${PROJECT}/${STATE}"
[ ! -f "$STATE_PATH" ] && { echo "ERROR: state file not found: $STATE_PATH" >&2; exit 1; }

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

case "$STATUS" in
  in_progress)
    NEW_ENTRY=$(jq -n --arg s "$STATUS" --arg t "$NOW" '{"status": $s, "started_at": $t}') ;;
  complete)
    STARTED=$(jq -r --arg k "$TICKET" '.statuses[$k].started_at // ""' "$STATE_PATH")
    if [ -n "$PR_URL" ]; then
      NEW_ENTRY=$(jq -n --arg s "$STATUS" --arg p "$PR_URL" --arg t "$NOW" --arg st "$STARTED" \
        '{"status": $s, "pr_url": $p, "started_at": $st, "completed_at": $t}')
    else
      NEW_ENTRY=$(jq -n --arg s "$STATUS" --arg t "$NOW" --arg st "$STARTED" \
        '{"status": $s, "started_at": $st, "completed_at": $t}')
    fi ;;
  skipped|failed|blocked|needs-decision)
    STARTED=$(jq -r --arg k "$TICKET" '.statuses[$k].started_at // ""' "$STATE_PATH")
    if [ -n "$REASON" ]; then
      NEW_ENTRY=$(jq -n --arg s "$STATUS" --arg r "$REASON" --arg t "$NOW" --arg st "$STARTED" \
        '{"status": $s, "reason": $r, "started_at": $st, "completed_at": $t}')
    else
      NEW_ENTRY=$(jq -n --arg s "$STATUS" --arg t "$NOW" --arg st "$STARTED" \
        '{"status": $s, "started_at": $st, "completed_at": $t}')
    fi ;;
  pending)
    NEW_ENTRY=$(jq -n --arg s "$STATUS" '{"status": $s}') ;;
  *)
    echo "ERROR: invalid status '$STATUS' — must be pending|in_progress|complete|skipped|failed|blocked|needs-decision" >&2
    exit 1 ;;
esac

# Every terminal entry has a receipt field, even when no artifact was supplied.
case "$STATUS" in
  complete|skipped|failed|blocked|needs-decision)
    NEW_ENTRY=$(printf '%s\n' "$NEW_ENTRY" | jq --arg receipt "$RECEIPT" '. + {receipt:$receipt}') ;;
esac

UPDATED_JSON=$(jq \
  --arg k "$TICKET" \
  --arg status "$STATUS" \
  --argjson entry "$NEW_ENTRY" \
  '
  .statuses[$k] = $entry |
  if $status == "in_progress" then .current = $k
  elif (.current == $k) then .current = null
  else . end |
  (if $status == "skipped" and ($entry | has("reason")) then
    .skip_reasons[$k] = $entry.reason else . end) |
  .metrics = {
    complete: ([.statuses | to_entries[] | select(.value.status == "complete")] | length),
    skipped:  ([.statuses | to_entries[] | select(.value.status == "skipped")]  | length),
    failed:   ([.statuses | to_entries[] | select(.value.status == "failed")]   | length),
    blocked:  ([.statuses | to_entries[] | select(.value.status == "blocked")]  | length),
    "needs-decision": ([.statuses | to_entries[] | select(.value.status == "needs-decision")] | length),
    pending:  ([.statuses | to_entries[] | select(.value.status == "pending")]  | length)
  }
  ' "$STATE_PATH")

echo "$UPDATED_JSON" > "$STATE_PATH"

git -C "$PROJECT" add "$STATE" 2>/dev/null && \
  git -C "$PROJECT" commit -m "batch(state): $TICKET → $STATUS" 2>/dev/null || \
  echo "WARN: batch state commit failed (non-blocking) — state file updated on disk" >&2

echo "BATCH_UPDATED: $TICKET → $STATUS"
