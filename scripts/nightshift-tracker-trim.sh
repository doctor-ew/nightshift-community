#!/usr/bin/env bash
# nightshift-tracker-trim.sh — print only the "## Pipeline Stages" section of the tracker.
#
# The tracker accumulates a Decisions Made log and Remaining Work notes that an
# orchestrator re-entering mid-pipeline does not need — it only needs to know which
# stage is next. This emits just the stage table so a resume reads the minimum.
#
# Usage: nightshift-tracker-trim.sh <task-key>
# Output: stdout (the Pipeline Stages section). Silent exit 0 if the tracker absent.
set -euo pipefail

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK="${1:-}"
[ -z "$TASK" ] && exit 0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$TASK")

TRACKER="${STATE_DIR}/${TASK}.md"
[ -f "$TRACKER" ] || exit 0

awk '/^## Pipeline Stages/{p=1} p && /^## / && !/^## Pipeline Stages/{p=0} p' "$TRACKER"
