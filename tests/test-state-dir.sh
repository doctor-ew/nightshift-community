#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOLVER="${REPO_DIR}/scripts/nightshift-state-dir.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-state-dir.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_eq() { [ "$1" = "$2" ] || fail "expected '$2', got '$1'"; }

fresh="$TMP_ROOT/fresh"
mkdir -p "$fresh"
fresh_abs="$(cd "$fresh" && pwd)"
assert_eq "$("$RESOLVER" --project "$fresh" --create)" "$fresh_abs/.nightshift"
[ -d "$fresh/.nightshift" ] || fail 'fresh canonical state directory was not created'
[ ! -e "$fresh/.claude/task-progress" ] || fail 'fresh resolution created legacy state'

legacy="$TMP_ROOT/legacy"
mkdir -p "$legacy/.claude/task-progress"
touch "$legacy/.claude/task-progress/old-run.md"
legacy_abs="$(cd "$legacy" && pwd)"
assert_eq "$("$RESOLVER" --project "$legacy" --task old-run)" "$legacy_abs/.claude/task-progress"

legacy_drew="$TMP_ROOT/legacy-drew"
mkdir -p "$legacy_drew/.drew"
touch "$legacy_drew/.drew/old-run.md"
legacy_drew_abs="$(cd "$legacy_drew" && pwd)"
assert_eq "$("$RESOLVER" --project "$legacy_drew" --task old-run)" "$legacy_drew_abs/.drew"

both="$TMP_ROOT/both"
mkdir -p "$both/.nightshift" "$both/.drew" "$both/.claude/task-progress"
touch "$both/.nightshift/current.md" "$both/.drew/old-run.md" "$both/.claude/task-progress/legacy-run.md"
both_abs="$(cd "$both" && pwd)"
assert_eq "$("$RESOLVER" --project "$both" --task current)" "$both_abs/.nightshift"
assert_eq "$("$RESOLVER" --project "$both" --task old-run)" "$both_abs/.drew"
assert_eq "$("$RESOLVER" --project "$both" --task legacy-run)" "$both_abs/.claude/task-progress"
assert_eq "$("$RESOLVER" --project "$both" --task new-run)" "$both_abs/.nightshift"
assert_eq "$("$RESOLVER" --project "$both" --all | tr '\n' ' ')" "$both_abs/.nightshift $both_abs/.drew $both_abs/.claude/task-progress "

legacy_batch="$TMP_ROOT/legacy-batch"
mkdir -p "$legacy_batch/.claude/task-progress"
printf '%s\n' '{"tickets":["old-run"],"statuses":{"old-run":{"status":"pending"}}}' > "$legacy_batch/.claude/task-progress/batch-20260905-2200.json"
batch_output=$(CLAUDE_PROJECT_DIR="$legacy_batch" "${REPO_DIR}/scripts/nightshift-batch-init.sh" --resume batch-20260905-2200.json)
case "$batch_output" in
  *"BATCH_STATE_PATH: .claude/task-progress/batch-20260905-2200.json"*) ;;
  *) fail "legacy batch state was not selected: $batch_output" ;;
esac

drew_batch="$TMP_ROOT/old-batch"
mkdir -p "$drew_batch/.drew"
printf '%s\n' '{"tickets":["old-run"],"statuses":{"old-run":{"status":"pending"}}}' > "$drew_batch/.drew/batch-20260905-2200.json"
batch_output=$(CLAUDE_PROJECT_DIR="$drew_batch" "${REPO_DIR}/scripts/nightshift-batch-init.sh" --resume batch-20260905-2200.json)
case "$batch_output" in
  *"BATCH_STATE_PATH: .drew/batch-20260905-2200.json"*) ;;
  *) fail "Drew batch state was not selected: $batch_output" ;;
esac

printf 'PASS: nightshift state-directory resolution\n'
