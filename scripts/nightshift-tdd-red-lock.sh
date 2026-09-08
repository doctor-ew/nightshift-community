#!/usr/bin/env bash
# nightshift-tdd-red-lock.sh — seal RED-phase test files under the nightshift-bot identity.
# Run after the RED phase is confirmed (failing tests written) and BEFORE any fix
# code is written. Records NIGHTSHIFT_RED_LOCK_SHA in the lock sidecar.
#
# Usage: nightshift-tdd-red-lock.sh <task-key>
#
# Strategy 1: stage test files declared in the spec's "Files to Change" table whose
#             Action mentions CREATE or TEST.
# Strategy 2 (fallback): any new test-shaped file added since the spec-lock commit.
# Also picks up any currently-staged test files.
set -euo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
TASK="${1:-}"
[ -z "$TASK" ] && { echo "RED_LOCK_SKIPPED: no task-key passed"; exit 0; }

SPEC_PATH="${PROJECT}/docs/${TASK}/SPEC.md"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPEC_LOCK_SHA=$(bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" --get NIGHTSHIFT_SPEC_LOCK_SHA)

STAGED=0

# Strategy 1: test files declared in the spec's Files to Change table.
if [ -f "$SPEC_PATH" ]; then
  while IFS= read -r line; do
    FILE_PATH=$(echo "$line" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2}' | tr -d '`')
    ACTION=$(echo "$line" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3}' | tr '[:lower:]' '[:upper:]')
    if [ -n "$FILE_PATH" ] && echo "$ACTION" | grep -qE "(CREATE|TEST)"; then
      FULL_PATH="${PROJECT}/${FILE_PATH}"
      if [ -f "$FULL_PATH" ]; then
        git -C "$PROJECT" add "$FULL_PATH" 2>/dev/null && STAGED=$((STAGED+1)) || true
      fi
    fi
  done < <(grep '|' "$SPEC_PATH" 2>/dev/null || true)
fi

# Strategy 2: new test-shaped files added since the spec-lock commit.
if [ -n "$SPEC_LOCK_SHA" ]; then
  while IFS= read -r f; do
    git -C "$PROJECT" add "$f" 2>/dev/null && STAGED=$((STAGED+1)) || true
  done < <(git -C "$PROJECT" diff --name-only --diff-filter=A "${SPEC_LOCK_SHA}..HEAD" 2>/dev/null \
    | grep -E "(\.test\.|\.spec\.|_test\.|Test\.|/tests?/)" || true)
fi

# Pick up anything already staged that looks like a test.
ALREADY_STAGED=$(git -C "$PROJECT" diff --cached --name-only 2>/dev/null \
  | grep -E "(\.test\.|\.spec\.|_test\.|Test\.|test-|test_|/tests?/)" | wc -l | xargs)
STAGED=$((STAGED + ALREADY_STAGED))

if git -C "$PROJECT" diff --cached --quiet 2>/dev/null; then
  echo "RED_LOCK_SKIPPED: no test files to stage"
  exit 0
fi

git -C "$PROJECT" \
  -c user.name="nightshift-bot" \
  -c user.email="nightshift-bot@local" \
  commit --no-gpg-sign \
  -m "lock(${TASK}): seal RED-phase tests — RED verified [nightshift-bot]" \
  2>/dev/null

LOCK_SHA=$(git -C "$PROJECT" rev-parse --short HEAD 2>/dev/null)
bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" NIGHTSHIFT_RED_LOCK_SHA "$LOCK_SHA"

echo "RED_LOCK_SHA: ${LOCK_SHA}"
