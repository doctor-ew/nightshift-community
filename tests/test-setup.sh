#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
if bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP" </dev/null > "$TEMP/result"; then exit 1; fi
jq -e '.code == "CONFIG_INCOMPLETE" and (.missing | length > 0)' "$TEMP/result"
cp "$ROOT/nightshift.toml" "$TEMP/nightshift.toml"
cp "$ROOT/routing.json" "$TEMP/routing.json"
bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP" --migrate
cmp "$ROOT/nightshift.toml" "$TEMP/nightshift.toml"
cmp "$TEMP/.nightshift.toml" "$TEMP/nightshift.toml"
bash "$ROOT/scripts/nightshift-manifest-validate.sh" --project "$TEMP"
printf '\n[runtime]\nprovider = "claude"\nmodel = "sonnet"\n' >> "$TEMP/.nightshift.toml"
bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP" --read | jq -e '.runtime.provider == "claude"'
# Canonical takes precedence even when a legacy file would validate.
printf '\n[policy]\n' >> "$TEMP/.nightshift.toml"
if bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP" --read > "$TEMP/result"; then exit 1; fi
jq -e '.code == "CONFIG_INVALID"' "$TEMP/result"
mkdir "$TEMP/private"
cp "$ROOT/nightshift.toml" "$TEMP/private/nightshift.toml"
chmod 600 "$TEMP/private/nightshift.toml"
cp "$ROOT/routing.json" "$TEMP/private/routing.json"
bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP/private" --migrate
python3 -c 'import os,stat,sys; assert stat.S_IMODE(os.stat(sys.argv[1]).st_mode) == 0o600' "$TEMP/private/.nightshift.toml"
printf '\n[runtime]\nprovider = 42\n' >> "$TEMP/private/.nightshift.toml"
if bash "$ROOT/scripts/nightshift-setup.sh" --project "$TEMP/private" --read > "$TEMP/result"; then exit 1; fi
jq -e '.code == "CONFIG_INVALID"' "$TEMP/result"
printf 'PASS: setup migration and unattended validation\n'
