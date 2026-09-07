#!/usr/bin/env bash
# nightshift-context-check.sh — check the context budget at stage entry.
#
# Usage: nightshift-context-check.sh <stage-name> [task-key]
# Exit:  0 = OK, 1 = WARN (<=50% remaining), 2 = BLOCK (<=10% remaining)
#
# Reads CLAUDE_CONTEXT_REMAINING_PERCENT (injected by the harness). When the budget
# is low it tells the orchestrator to compact or resume rather than pushing a stage
# into a context wall. Zero deps; a no-op when the env var is absent.
STAGE="${1:-unknown}"
TASK="${2:-}"
REMAINING="${CLAUDE_CONTEXT_REMAINING_PERCENT:-}"

[ -z "$REMAINING" ] && exit 0
PCT=$(echo "$REMAINING" | grep -oE '^[0-9]+' || true)
[ -z "$PCT" ] && exit 0

if [ "$PCT" -le 10 ]; then
  echo "[nightshift] Context budget exhausted (~${PCT}% remaining). Compact, then resume from here:"
  echo "  /nightshift-eng ${TASK} --from ${STAGE}"
  exit 2
elif [ "$PCT" -le 50 ]; then
  echo "[nightshift] Context budget low (~${PCT}% remaining) — consider /compact before the next stage."
  exit 1
fi
exit 0
