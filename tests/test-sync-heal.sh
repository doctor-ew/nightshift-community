#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-heal.XXXXXX")"
trap 'rm -rf "$FIXTURE"' EXIT
ARGS=(--runtime all --target "$FIXTURE/claude" --codex-target "$FIXTURE/codex" --nightshift-target "$FIXTURE/runtime" --bin-target "$FIXTURE/bin")
bash "$ROOT/install.sh" "${ARGS[@]}" > "$FIXTURE/install.log" 2>&1
unlink "$FIXTURE/runtime/scripts/nightshift-spec-source.py"
bash "$ROOT/install.sh" "${ARGS[@]}" --repair > "$FIXTURE/repair.log" 2>&1
test -L "$FIXTURE/runtime/scripts/nightshift-spec-source.py"
# Repair must not overwrite custom non-link files.
unlink "$FIXTURE/runtime/scripts/nightshift-spec-source.py"
printf 'custom helper\n' > "$FIXTURE/runtime/scripts/nightshift-spec-source.py"
if bash "$ROOT/install.sh" "${ARGS[@]}" --repair > "$FIXTURE/conflict.log" 2>&1; then
  echo 'FAIL: custom helper overwritten'; exit 1
fi
test "$(cat "$FIXTURE/runtime/scripts/nightshift-spec-source.py")" = 'custom helper'
NIGHTSHIFT_HOME="$FIXTURE/runtime" "$FIXTURE/bin/nightshift" --sync --help | grep -q -- '--heal'
echo 'PASS: sync alias, missing-link repair and custom-file preservation'
