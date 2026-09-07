#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VALIDATOR="$REPO_DIR/scripts/nightshift-manifest-validate.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-manifest.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
mkdir -p "$TMP_ROOT/valid"; cp "$REPO_DIR/nightshift.toml" "$TMP_ROOT/valid/nightshift.toml"; printf '{}' > "$TMP_ROOT/valid/routing.json"
"$VALIDATOR" --project "$TMP_ROOT/valid" | jq -e '.status == "ok" and .production_url == "https://example.invalid"' >/dev/null || fail 'valid manifest was rejected'
if "$VALIDATOR" --project "$TMP_ROOT/missing" | jq -e '.code == "MANIFEST_MISSING"' >/dev/null; then fail 'missing directory unexpectedly validated'; fi
mkdir -p "$TMP_ROOT/invalid"; cp "$TMP_ROOT/valid/nightshift.toml" "$TMP_ROOT/invalid/nightshift.toml"; printf '{}' > "$TMP_ROOT/invalid/routing.json"
sed -i.bak 's/allow_heuristic_production_target = false/allow_heuristic_production_target = true/' "$TMP_ROOT/invalid/nightshift.toml"
if "$VALIDATOR" --project "$TMP_ROOT/invalid" | jq -e '.code == "MANIFEST_INVALID"' >/dev/null; then fail 'heuristic production target unexpectedly validated'; fi
printf 'PASS: Nightshift manifest validation\n'
