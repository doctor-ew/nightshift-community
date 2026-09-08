#!/usr/bin/env bash
# nightshift-crash-check.sh — detect leftover state from a crashed/killed pipeline
# session, so /nightshift-eng and /nightshift-implement can offer cleanup on resume.
#
# Two kinds of orphaned state are surfaced:
#   1. Stale scope-freeze   — a .active-scope-<TASK> file whose pipeline is no
#      longer in-progress (tracker shows no ⏳ row, or no ACTIVE-* exists). An
#      orphan silently blocks every Edit/Write via the global scope-freeze hook.
#   2. Interrupted stage     — an ACTIVE-* file with NIGHTSHIFT_PHASE != complete whose
#      tracker still has a ⏳ in-progress row.
#
# Output (one finding per line, machine-parseable):
#   STALE_SCOPE: <task> <path>
#   INTERRUPTED: <task> <phase>
#   CLEAN: no orphaned pipeline state
#
# Fail-open: any error / non-pipeline project prints CLEAN.
PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TP=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT")
[ -d "$TP" ] || { echo "CLEAN: no orphaned pipeline state"; exit 0; }

FOUND=0

# --- in-progress tickets (from ACTIVE-* with phase != complete + ⏳ tracker row)
declare -a LIVE_TASKS=()
shopt -s nullglob 2>/dev/null || true
for ACTIVE in "$TP"/ACTIVE-*; do
  [ -f "$ACTIVE" ] || continue
  TASK=$(grep "^NIGHTSHIFT_TICKET=" "$ACTIVE" 2>/dev/null | head -1 | cut -d= -f2)
  PHASE=$(grep "^NIGHTSHIFT_PHASE=" "$ACTIVE" 2>/dev/null | head -1 | cut -d= -f2)
  [ -z "$TASK" ] && continue
  [ "$PHASE" = "complete" ] && continue
  TRACKER="${TP}/${TASK}.md"
  if [ -f "$TRACKER" ] && grep -q '^⏳' "$TRACKER" 2>/dev/null; then
    echo "INTERRUPTED: ${TASK} ${PHASE:-unknown}"
    LIVE_TASKS+=("$TASK")
    FOUND=1
  fi
done

# --- stale scope files (active-scope with no corresponding live ticket)
for SCOPE in "$TP"/.active-scope-*; do
  [ -f "$SCOPE" ] || continue
  STASK="${SCOPE##*/.active-scope-}"
  IS_LIVE=0
  for lt in "${LIVE_TASKS[@]}"; do
    [ "$lt" = "$STASK" ] && IS_LIVE=1 && break
  done
  if [ "$IS_LIVE" -eq 0 ]; then
    echo "STALE_SCOPE: ${STASK} ${SCOPE#$PROJECT/}"
    FOUND=1
  fi
done

[ "$FOUND" -eq 0 ] && echo "CLEAN: no orphaned pipeline state"
exit 0
