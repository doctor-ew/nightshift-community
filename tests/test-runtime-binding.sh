#!/usr/bin/env bash
# Execute the canonical template against a deliberately unusable older helper home.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-runtime.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/older/scripts"
printf 'raise SystemExit("older helper was invoked")\n' > "$TMP/older/scripts/nightshift-stage-args.py"
line=$(rg '^STAGE_ARGS=' "$ROOT/commands/nightshift-eng.md")
result=$(NIGHTSHIFT_RUNTIME_HOME="$ROOT" NIGHTSHIFT_HOME="$TMP/older" ARGUMENTS='gh:154' bash -c "$line; printf '%s' \"\$STAGE_ARGS\"")
jq -e '.auth=="subscription" and .arguments=="gh:154"' <<< "$result" >/dev/null
# Without an explicit source runtime, ordinary installed operation still works.
cp "$ROOT/scripts/nightshift-stage-args.py" "$TMP/older/scripts/nightshift-stage-args.py"
result=$(env -u NIGHTSHIFT_RUNTIME_HOME NIGHTSHIFT_HOME="$TMP/older" ARGUMENTS='gh:154' bash -c "$line; printf '%s' \"\$STAGE_ARGS\"")
jq -e '.arguments=="gh:154"' <<< "$result" >/dev/null
printf 'PASS: canonical runtime selection and installed fallback\n'
