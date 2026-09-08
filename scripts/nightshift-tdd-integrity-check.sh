#!/usr/bin/env bash
# nightshift-tdd-integrity-check.sh — verify no non-bot commit touched locked paths after
# the lock point. Run at /nightshift-review before the lens pass.
#
# Usage: nightshift-tdd-integrity-check.sh <task-key>
# Outputs: TDD_INTEGRITY: PASS | TDD_INTEGRITY: FAIL | TDD_INTEGRITY: SKIPPED
# bash 3.x compatible (macOS default shell — no associative arrays).
set -uo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
TASK="${1:-}"
[ -z "$TASK" ] && { echo "TDD_INTEGRITY: SKIPPED — no task-key passed"; exit 0; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPEC_LOCK_SHA=$(bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" --get NIGHTSHIFT_SPEC_LOCK_SHA)
RED_LOCK_SHA=$(bash "${SCRIPT_DIR}/nightshift-lock-field.sh" "$TASK" --get NIGHTSHIFT_RED_LOCK_SHA)

# No lock SHAs → this task didn't run the TDD locks. Skip gracefully.
if [ -z "$SPEC_LOCK_SHA" ] && [ -z "$RED_LOCK_SHA" ]; then
  echo "TDD_INTEGRITY: SKIPPED — no lock SHAs recorded for ${TASK}. Run nightshift-implement with TDD locks to enable."
  exit 0
fi

RANGE_START="${SPEC_LOCK_SHA:-$RED_LOCK_SHA}"

LOCKED_PATHS_FILE="$(mktemp)"
DEDUPED_PATHS_FILE="$(mktemp)"
VIOLATIONS_FILE="$(mktemp)"
trap 'rm -f "$LOCKED_PATHS_FILE" "$DEDUPED_PATHS_FILE" "$VIOLATIONS_FILE"' EXIT

# SPEC_LOCK always locks the spec for this task, plus any files in the lock commit.
if [ -n "$SPEC_LOCK_SHA" ]; then
  echo "docs/${TASK}/SPEC.md" >> "$LOCKED_PATHS_FILE"
  git -C "$PROJECT" diff-tree --no-commit-id -r --name-only "$SPEC_LOCK_SHA" 2>/dev/null \
    >> "$LOCKED_PATHS_FILE" || true
fi

# RED_LOCK locks whatever test files were committed in that commit.
if [ -n "$RED_LOCK_SHA" ]; then
  git -C "$PROJECT" diff-tree --no-commit-id -r --name-only "$RED_LOCK_SHA" 2>/dev/null \
    >> "$LOCKED_PATHS_FILE" || true
fi

sort -u "$LOCKED_PATHS_FILE" > "$DEDUPED_PATHS_FILE"
LOCKED_COUNT=$(wc -l < "$DEDUPED_PATHS_FILE" | xargs)

if [ "$LOCKED_COUNT" -eq 0 ]; then
  echo "TDD_INTEGRITY: PASS — no locked paths to check (lock commits were empty)"
  exit 0
fi

SPEC_LOCK_FULL=""
RED_LOCK_FULL=""
[ -n "$SPEC_LOCK_SHA" ] && SPEC_LOCK_FULL=$(git -C "$PROJECT" rev-parse "${SPEC_LOCK_SHA}" 2>/dev/null || true)
[ -n "$RED_LOCK_SHA" ]  && RED_LOCK_FULL=$(git -C "$PROJECT" rev-parse "${RED_LOCK_SHA}" 2>/dev/null || true)

while IFS= read -r commit_sha; do
  [ "$commit_sha" = "$SPEC_LOCK_FULL" ] && continue
  [ "$commit_sha" = "$RED_LOCK_FULL" ]  && continue

  AUTHOR_EMAIL=$(git -C "$PROJECT" log -1 --format="%ae" "$commit_sha" 2>/dev/null || true)
  [ "$AUTHOR_EMAIL" = "nightshift-bot@local" ] && continue

  SHORT_SHA=$(git -C "$PROJECT" rev-parse --short "$commit_sha" 2>/dev/null || true)
  COMMIT_MSG=$(git -C "$PROJECT" log -1 --format="%s" "$commit_sha" 2>/dev/null || true)
  COMMIT_TIME=$(git -C "$PROJECT" log -1 --format="%ci" "$commit_sha" 2>/dev/null || true)

  CHANGED_FILES=$(git -C "$PROJECT" diff-tree --no-commit-id -r --name-only "$commit_sha" 2>/dev/null || true)
  while IFS= read -r lp; do
    [ -z "$lp" ] && continue
    if echo "$CHANGED_FILES" | grep -qxF "$lp"; then
      echo "  VIOLATION: commit ${SHORT_SHA} by ${AUTHOR_EMAIL} at ${COMMIT_TIME} — touched locked path: ${lp} (${COMMIT_MSG})" \
        >> "$VIOLATIONS_FILE"
    fi
  done < "$DEDUPED_PATHS_FILE"
done < <(git -C "$PROJECT" log "${RANGE_START}..HEAD" --format="%H" 2>/dev/null || true)

VIOLATION_COUNT=$(wc -l < "$VIOLATIONS_FILE" | xargs)

if [ "$VIOLATION_COUNT" -eq 0 ]; then
  echo "TDD_INTEGRITY: PASS — no non-bot commits touched locked paths after lock point"
else
  echo "TDD_INTEGRITY: FAIL — ${VIOLATION_COUNT} violation(s) detected:"
  cat "$VIOLATIONS_FILE"
  echo ""
  echo "Locked paths checked:"
  sed 's/^/  /' "$DEDUPED_PATHS_FILE"
  echo ""
  echo "To resolve: revert the offending commits, or update the spec to reflect the intended change and re-run the spec lock."
fi
