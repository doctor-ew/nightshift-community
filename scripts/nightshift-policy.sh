#!/usr/bin/env bash
# Policy gateway for all commands issued by the factory controller.
set -euo pipefail

usage() { echo "usage: nightshift-policy.sh check --action ACTION --worktree DIR --log FILE [--command TEXT] [--confirmation-token TOKEN] [--confirmed-at ISO-8601]" >&2; exit 64; }
[ "${1:-}" = check ] || usage; shift
ACTION=""; WORKTREE=""; LOG=""; COMMAND_TEXT=""; TOKEN=""; CONFIRMED_AT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --action) ACTION="${2:-}"; shift 2 ;;
    --worktree) WORKTREE="${2:-}"; shift 2 ;;
    --log) LOG="${2:-}"; shift 2 ;;
    --command) COMMAND_TEXT="${2:-}"; shift 2 ;;
    --confirmation-token) TOKEN="${2:-}"; shift 2 ;;
    --confirmed-at) CONFIRMED_AT="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$ACTION" ] && [ -n "$WORKTREE" ] && [ -n "$LOG" ] || usage
[ -d "$WORKTREE" ] || { echo "worktree does not exist: $WORKTREE" >&2; exit 66; }
mkdir -p "$(dirname "$LOG")"

DECISION="deny"; REASON="unknown action"
case "$ACTION" in
  worktree-command)
    case "$WORKTREE" in /*) DECISION="allow"; REASON="normal command inside assigned worktree is unattended";; esac ;;
  production-deploy)
    if [ -n "${NIGHTSHIFT_PRODUCTION_CONFIRMATION_TOKEN:-}" ] && [ "$TOKEN" = "$NIGHTSHIFT_PRODUCTION_CONFIRMATION_TOKEN" ] && [ -n "$CONFIRMED_AT" ] && command -v python3 >/dev/null 2>&1 && python3 - "$CONFIRMED_AT" <<'PY'
import sys
from datetime import datetime, timezone
try:
    confirmed = datetime.fromisoformat(sys.argv[1].replace('Z', '+00:00'))
    assert abs((datetime.now(timezone.utc) - confirmed).total_seconds()) <= 300
except Exception:
    raise SystemExit(1)
PY
    then DECISION="allow"; REASON="fresh production confirmation token accepted"
    else REASON="production deployment requires a fresh confirmation token"; fi ;;
  permanent-removal|history-rewrite) REASON="$ACTION is denied by factory policy" ;;
esac

jq -cn --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg action "$ACTION" --arg worktree "$WORKTREE" \
  --arg command "$COMMAND_TEXT" --arg decision "$DECISION" --arg reason "$REASON" \
  '{timestamp:$timestamp,action:$action,worktree:$worktree,command:$command,decision:$decision,reason:$reason}' >> "$LOG"
jq -cn --arg action "$ACTION" --arg decision "$DECISION" --arg reason "$REASON" '{action:$action,decision:$decision,reason:$reason}'
[ "$DECISION" = allow ]
