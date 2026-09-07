#!/usr/bin/env bash
# nightshift-state-dir.sh — resolve Nightshift's project-local runtime state directory.
#
# New runs use <project>/.nightshift. Legacy tasks may remain in .drew or
# <project>/.claude/task-progress, so callers can resume them without copying,
# moving, or deleting state.
#
# Usage: nightshift-state-dir.sh [--project DIR] [--task KEY] [--create] [--all]

set -euo pipefail

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TASK=""
CREATE="no"
ALL="no"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) shift; PROJECT="${1:?--project requires a directory}" ;;
    --task) shift; TASK="${1:?--task requires a task key}" ;;
    --create) CREATE="yes" ;;
    --all) ALL="yes" ;;
    -h|--help)
      echo "Usage: nightshift-state-dir.sh [--project DIR] [--task KEY] [--create] [--all]"
      exit 0
      ;;
    *) echo "nightshift-state-dir: unknown option: $1" >&2; exit 64 ;;
  esac
  shift
done

PROJECT="$(cd "$PROJECT" && pwd)"
CANONICAL="${PROJECT}/.nightshift"
LEGACY_DREW="${PROJECT}/.drew"
LEGACY_CLAUDE="${PROJECT}/.claude/task-progress"

if [ "$ALL" = "yes" ]; then
  [ "$CREATE" = "yes" ] && mkdir -p "$CANONICAL"
  printf '%s\n' "$CANONICAL"
  [ -d "$LEGACY_DREW" ] && printf '%s\n' "$LEGACY_DREW"
  [ -d "$LEGACY_CLAUDE" ] && printf '%s\n' "$LEGACY_CLAUDE"
  exit 0
fi

RESULT="$CANONICAL"

if [ -n "$TASK" ]; then
  # Prefer canonical state when both homes contain the same tracker.
  if [ -f "${CANONICAL}/${TASK}" ] || [ -f "${CANONICAL}/${TASK}.md" ]; then
    RESULT="$CANONICAL"
  elif [ -f "${LEGACY_DREW}/${TASK}" ] || [ -f "${LEGACY_DREW}/${TASK}.md" ]; then
    RESULT="$LEGACY_DREW"
  elif [ -f "${LEGACY_CLAUDE}/${TASK}" ] || [ -f "${LEGACY_CLAUDE}/${TASK}.md" ]; then
    RESULT="$LEGACY_CLAUDE"
  fi
elif [ ! -d "$CANONICAL" ] && [ -d "$LEGACY_DREW" ]; then
  # Shared operations keep using an all-legacy project until canonical state
  # exists; the first state-writing caller can opt into --create.
  RESULT="$LEGACY_DREW"
elif [ ! -d "$CANONICAL" ] && [ -d "$LEGACY_CLAUDE" ]; then
  RESULT="$LEGACY_CLAUDE"
fi

if [ "$CREATE" = "yes" ] && [ "$RESULT" = "$CANONICAL" ]; then
  mkdir -p "$CANONICAL"
fi

printf '%s\n' "$RESULT"
