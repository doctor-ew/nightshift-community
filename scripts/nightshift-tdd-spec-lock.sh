#!/usr/bin/env bash
# nightshift-tdd-spec-lock.sh — seal docs/<task-key>/SPEC.md under the nightshift-bot identity
# after spec approval. Records NIGHTSHIFT_SPEC_LOCK_SHA in the lock sidecar.
#
# Usage: nightshift-tdd-spec-lock.sh <task-key>
#
# Always creates a lock commit (--allow-empty if SPEC.md is unchanged) so a lock
# SHA always exists regardless of working-tree state. The integrity check at
# /nightshift-review uses this SHA as the start of the range it audits.
set -euo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
TASK="${1:-}"
[ -z "$TASK" ] && { echo "SPEC_LOCK_SKIPPED: no task-key passed"; exit 0; }

SPEC_PATH="${PROJECT}/docs/${TASK}/SPEC.md"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$SPEC_PATH" ]; then
  echo "SPEC_LOCK_SKIPPED: SPEC.md not found at $SPEC_PATH"
  exit 0
fi

# Adopted specs seal only the two public artifacts. Refuse an unrelated index
# instead of silently committing another task's staged changes.
SCENARIO_PATH="${PROJECT}/docs/${TASK}/behavior-scenarios.json"
if [ -e "$SCENARIO_PATH" ] || [ -L "$SCENARIO_PATH" ]; then
  python3 "$SCRIPT_DIR/nightshift-behavior-proof.py" validate --project "$PROJECT" --task "$TASK" --scenarios "$SCENARIO_PATH" >/dev/null
  STAGED_PATHS=$(mktemp)
  trap 'rm -f -- "$STAGED_PATHS"' EXIT
  git -C "$PROJECT" diff --cached --name-only -z > "$STAGED_PATHS"
  while IFS= read -r -d '' staged; do
    case "$staged" in "docs/$TASK/SPEC.md"|"docs/$TASK/behavior-scenarios.json") ;;
      *) echo 'SPEC_LOCK_FAILED: unrelated staged paths must remain outside the seal' >&2; exit 1;;
    esac
  done < "$STAGED_PATHS"
  git -C "$PROJECT" add -- "$SPEC_PATH" "$SCENARIO_PATH"
else
  git -C "$PROJECT" add -- "$SPEC_PATH"
fi

# Always create a lock commit — --allow-empty guarantees a real SHA is recorded.
git -C "$PROJECT" \
  -c user.name="nightshift-bot" \
  -c user.email="nightshift-bot@local" \
  commit --no-gpg-sign --allow-empty \
  -m "lock(${TASK}): seal SPEC.md — spec approved [nightshift-bot]" \
  2>/dev/null

LOCK_SHA=$(git -C "$PROJECT" rev-parse --short HEAD 2>/dev/null)

bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" NIGHTSHIFT_SPEC_LOCK_SHA "$LOCK_SHA"

echo "SPEC_LOCK_SHA: ${LOCK_SHA}"
