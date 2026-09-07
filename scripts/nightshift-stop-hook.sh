#!/usr/bin/env bash
# nightshift-stop-hook.sh — Stop hook for the nightshift-* pipeline. Blocks session close
# while a pipeline stage is still ⏳ in-progress in the local tracker, so a
# half-finished stage isn't silently abandoned. Fail-open on every error.
#
# Wiring: Claude Code Stop hook (settings.json hooks.Stop). Install with
#   install.sh --with-hook  (adds it alongside the PreToolUse hooks).
#
# Detection: scans $PROJECT/.claude/task-progress/ACTIVE-* for NIGHTSHIFT_TICKET +
# NIGHTSHIFT_PHASE, then checks the matching .claude/task-progress/<TICKET>.md tracker
# for a row marked '⏳' (in-progress).
#
# Exits:
#   2 — in-progress stage detected (blocks close, prints warning to stderr)
#   0 — anything else (no ACTIVE file, phase complete, no ⏳ row, parse failure,
#       missing tracker/dir — never blocks on a non-pipeline project)

# Guard: if this turn was itself triggered by a previous stop-hook block, don't
# re-block — otherwise the hook loops until Claude Code's block cap is hit.
INPUT=$(cat)
if echo "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TP=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT_DIR")
[ -d "$TP" ] || exit 0

shopt -s nullglob 2>/dev/null || true
ACTIVE_FILES=("$TP"/ACTIVE-*)
[ ${#ACTIVE_FILES[@]} -eq 0 ] && exit 0

for ACTIVE in "${ACTIVE_FILES[@]}"; do
  [ -f "$ACTIVE" ] || continue
  TASK=$(grep "^NIGHTSHIFT_TICKET=" "$ACTIVE" 2>/dev/null | head -1 | cut -d= -f2)
  PHASE=$(grep "^NIGHTSHIFT_PHASE=" "$ACTIVE" 2>/dev/null | head -1 | cut -d= -f2)
  [ -z "$TASK" ] && continue
  [ "$PHASE" = "complete" ] && continue
  TRACKER="${TP}/${TASK}.md"
  [ -f "$TRACKER" ] || continue
  if grep -q '^⏳' "$TRACKER" 2>/dev/null; then
    STAGE=$(grep '^⏳' "$TRACKER" 2>/dev/null | head -1 | sed -E 's/^⏳[[:space:]]*//')
    echo "nightshift: stage still in progress for ${TASK} — ${STAGE}" >&2
    echo "Finish or explicitly halt the stage before closing (the tracker still shows ⏳)." >&2
    echo "To stop anyway, close again — this hook fails open on the second attempt." >&2
    exit 2
  fi
done

exit 0
