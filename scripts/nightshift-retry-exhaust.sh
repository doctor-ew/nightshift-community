#!/usr/bin/env bash
set -uo pipefail
# nightshift-retry-exhaust.sh — terminal skip sequence when an autonomous-mode stage burns
# its retry budget. No telemetry, no external emit — purely local bookkeeping.
#
# Usage: nightshift-retry-exhaust.sh <task-key> <stage> <reason>
#
# Does the parts a script CAN do deterministically:
#   1. Mark the stage blocked in the markdown tracker (if present).
#   2. Append the skip reason to the lock sidecar (RETRY_EXHAUST_REASON).
#   3. Print PIPELINE_SKIPPED: <task-key> stage '<stage>' — <reason>
#   4. Exit 0 (skip is a clean, non-failure outcome for the batch loop).
#
# The batch loop reads the PIPELINE_SKIPPED marker and records the ticket as skipped.

TASK="${1:-}"; STAGE="${2:-}"; REASON="${3:-}"
if [ -z "$TASK" ] || [ -z "$STAGE" ] || [ -z "$REASON" ]; then
  echo "ERROR: usage: nightshift-retry-exhaust.sh <task-key> <stage> <reason>" >&2
  exit 2
fi

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$TASK" --create)
TRACKER="${STATE_DIR}/${TASK}.md"

# 1. Mark the stage blocked in the tracker (best-effort; tracker format varies).
if [ -f "$TRACKER" ]; then
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # Handle both the emoji form (⬜/⏳ /nightshift-<stage>) and the checkbox form (- [ ] /<stage>).
  sed -i '' "s|^[⬜⏳] /[a-z-]*${STAGE}.*|❌ /${STAGE} — ${STAGE} [retry budget exhausted, $TS]|" "$TRACKER" 2>/dev/null || true
fi

# 2. Record the reason in the lock sidecar.
bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" RETRY_EXHAUST_REASON "${STAGE}: ${REASON}" 2>/dev/null || true

# 3 + 4. Marker + clean exit.
echo "PIPELINE_SKIPPED: ${TASK} stage '${STAGE}' — ${REASON}"
exit 0
