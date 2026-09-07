#!/usr/bin/env bash
# Deterministic gate controller for unattended Nightshift workers.
set -euo pipefail

usage() {
  echo "usage: nightshift-controller.sh run --ticket KEY --gate GATE --provider PROVIDER --worktree DIR --receipt FILE [--budget N] --attempt-command COMMAND [--repair-command COMMAND] [--terminal-status blocked|failed|needs-decision]" >&2
  exit 64
}

MODE="${1:-}"; shift || true
[ "$MODE" = run ] || usage
TICKET=""; GATE=""; PROVIDER=""; WORKTREE=""; RECEIPT=""; BUDGET=""; ATTEMPT=""; REPAIR=""; FAILURE_STATUS="failed"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ticket) TICKET="${2:-}"; shift 2 ;;
    --gate) GATE="${2:-}"; shift 2 ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --worktree) WORKTREE="${2:-}"; shift 2 ;;
    --receipt) RECEIPT="${2:-}"; shift 2 ;;
    --budget) BUDGET="${2:-}"; shift 2 ;;
    --attempt-command) ATTEMPT="${2:-}"; shift 2 ;;
    --repair-command) REPAIR="${2:-}"; shift 2 ;;
    --terminal-status) FAILURE_STATUS="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

[ -n "$TICKET" ] && [ -n "$GATE" ] && [ -n "$PROVIDER" ] && [ -n "$WORKTREE" ] && [ -n "$RECEIPT" ] && [ -n "$ATTEMPT" ] || usage
[ -d "$WORKTREE" ] || { echo "worktree does not exist: $WORKTREE" >&2; exit 66; }
case "$GATE" in implement|review|drift|qa) ;; *) echo "unsupported gate: $GATE" >&2; exit 64;; esac
case "$FAILURE_STATUS" in blocked|failed|needs-decision) ;; *) echo "invalid terminal status: $FAILURE_STATUS" >&2; exit 64;; esac

if [ -z "$BUDGET" ]; then
  MANIFEST="$(bash "$(dirname "$0")/nightshift-manifest-path.sh" --project "$WORKTREE")"
  [ -f "$MANIFEST" ] || { echo "nightshift.toml is required when --budget is omitted" >&2; exit 65; }
  BUDGET=$(awk -F= -v gate="$GATE" '
    /^\[repair_budgets\]$/ { in_section=1; next }
    /^\[/ { in_section=0 }
    in_section && $1 ~ "^[[:space:]]*" gate "[[:space:]]*$" { gsub(/[[:space:]]/, "", $2); print $2; exit }
  ' "$MANIFEST")
fi
[[ "$BUDGET" =~ ^[1-9][0-9]*$ ]] || { echo "invalid repair budget: $BUDGET" >&2; exit 64; }

mkdir -p "$(dirname "$RECEIPT")"
ATTEMPTS_FILE=$(mktemp "${TMPDIR:-/tmp}/nightshift-controller.XXXXXX")
trap 'rm -f "$ATTEMPTS_FILE"' EXIT
STATUS="failed"; NEXT_ACTION="inspect the final gate output and repair the smallest in-scope cause"
OUTPUT=""

# Planned commands are separate from actual isolation dispatcher invocations.
# A failed invocation does not establish whether the worker command executed.
write_receipt() {
  local changed attempts
  changed=$(git -C "$WORKTREE" status --short 2>/dev/null | jq -R . | jq -s .) || changed='[]'
  attempts=$(jq -s . "$ATTEMPTS_FILE")
  jq -n --arg ticket "$TICKET" --arg gate "$GATE" --arg provider "$PROVIDER" --arg worktree "$WORKTREE" \
    --arg status "$STATUS" --arg next_action "$NEXT_ACTION" --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg attempt_command "$ATTEMPT" --arg repair_command "$REPAIR" --arg output "$OUTPUT" \
    --argjson budget "$BUDGET" --argjson attempts "$attempts" --argjson changed_files "$changed" \
    '{ticket:$ticket,gate:$gate,status:$status,provider:$provider,worktree:$worktree,repair_budget:$budget,
      commands:{attempt:$attempt_command,repair:$repair_command},output:$output,attempts:$attempts,
      changed_files:$changed_files,next_action:$next_action,generated_at:$generated_at}' > "$RECEIPT"
}

block_run() {
  STATUS="blocked"; OUTPUT="$1"; NEXT_ACTION="$2"
  write_receipt
  echo "CONTROLLER_BLOCKED: $RECEIPT" >&2
  exit 1
}

POLICY="$(cd "$(dirname "$0")" && pwd)/nightshift-policy.sh"
POLICY_LOG="$(dirname "$RECEIPT")/policy-decisions.jsonl"
ISOLATE="$(cd "$(dirname "$0")" && pwd)/nightshift-isolate.sh"
IMAGE="${NIGHTSHIFT_WORKER_IMAGE:-}"
[ -x "$POLICY" ] || block_run "Policy gateway missing: $POLICY" "Restore the policy gateway before retrying."
[ -f "$ISOLATE" ] || block_run "Isolation runner missing: $ISOLATE" "Restore the isolation runner; host execution is disabled."
[ -n "$IMAGE" ] || block_run "NIGHTSHIFT_WORKER_IMAGE is not configured; no commands were executed." \
  "Configure NIGHTSHIFT_WORKER_IMAGE; host execution is disabled."
ISOLATION_ARGS=(run --worktree "$WORKTREE" --image "$IMAGE" --policy-log "$POLICY_LOG")
[ -z "${NIGHTSHIFT_CONTAINER_RUNTIME:-}" ] || ISOLATION_ARGS+=(--runtime "$NIGHTSHIFT_CONTAINER_RUNTIME")
[ -z "${NIGHTSHIFT_CREDENTIAL_PROFILE:-}" ] || ISOLATION_ARGS+=(--profile "$NIGHTSHIFT_CREDENTIAL_PROFILE")
[ -z "${NIGHTSHIFT_PROFILES_FILE:-}" ] || ISOLATION_ARGS+=(--profiles "$NIGHTSHIFT_PROFILES_FILE")

run_isolated() {
  "$POLICY" check --action worktree-command --worktree "$WORKTREE" --log "$POLICY_LOG" --command "$1" &&
    bash "$ISOLATE" "${ISOLATION_ARGS[@]}" -- bash -c "$1"
}
# Positive repair budgets remain caps on gate attempts, not counts of extra retries.
for attempt in $(seq 1 "$BUDGET"); do
  LOG=$(mktemp "${TMPDIR:-/tmp}/nightshift-gate.XXXXXX")
  if run_isolated "$ATTEMPT" >"$LOG" 2>&1; then
    RC=0
    STATUS="complete"
    NEXT_ACTION="continue to the next gate"
  else
    RC=$?
  fi
  OUTPUT=$(tail -c 8192 "$LOG")
  jq -cn --argjson attempt "$attempt" --arg command "$ATTEMPT" --argjson exit_code "$RC" --arg output "$OUTPUT" \
    '{attempt:$attempt,command:$command,invocation:"isolation",worker_execution:(if $exit_code == 0 then "confirmed" else "unknown" end),exit_code:$exit_code,output:$output}' >> "$ATTEMPTS_FILE"
  rm -f "$LOG"
  [ "$RC" -eq 0 ] && break
  if [ "$attempt" -lt "$BUDGET" ] && [ -n "$REPAIR" ]; then
    REPAIR_LOG=$(mktemp "${TMPDIR:-/tmp}/nightshift-repair.XXXXXX")
    if run_isolated "$REPAIR" >"$REPAIR_LOG" 2>&1; then REPAIR_RC=0; else REPAIR_RC=$?; fi
    jq -cn --argjson attempt "$attempt" --arg command "$REPAIR" --argjson exit_code "$REPAIR_RC" --arg output "$(tail -c 8192 "$REPAIR_LOG")" \
      '{repair_after_attempt:$attempt,command:$command,invocation:"isolation",worker_execution:(if $exit_code == 0 then "confirmed" else "unknown" end),exit_code:$exit_code,output:$output}' >> "$ATTEMPTS_FILE"
    rm -f "$REPAIR_LOG"
  fi
done

[ "$STATUS" = complete ] || STATUS="$FAILURE_STATUS"

write_receipt

case "$STATUS" in
  complete) echo "CONTROLLER_COMPLETE: $RECEIPT" ;;
  blocked|failed|needs-decision) echo "CONTROLLER_$(printf '%s' "$STATUS" | tr '[:lower:]' '[:upper:]'): $RECEIPT" >&2; exit 1 ;;
esac
