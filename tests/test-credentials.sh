#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PROFILES="$ROOT/scripts/nightshift-credentials.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-credentials.XXXXXX")"; trap 'rm -rf "$TMP_ROOT"' EXIT
mkdir -p "$TMP_ROOT/worktree"; LOG="$TMP_ROOT/policy.jsonl"
"$PROFILES" plan --profile offline --worktree "$TMP_ROOT/worktree" | jq -e '.credential_names == [] and .egress_allowlist == []' >/dev/null
printf '%s\n' '{"profiles":{"coding":{"credential_names":["GH_TOKEN"],"egress_allowlist":["github.com"]},"production":{"credential_names":["DEPLOY_TOKEN"],"egress_allowlist":[],"production":true}}}' > "$TMP_ROOT/profiles.json"
"$PROFILES" plan --profile coding --profiles "$TMP_ROOT/profiles.json" --worktree "$TMP_ROOT/worktree" | jq -e '.credential_names == ["GH_TOKEN"] and .egress_allowlist == ["github.com"] and .inject_values == false' >/dev/null
for BAD in '"*.github.com"' '"tickets.example.invalid"' '"127.0.0.1"' '"github.com\nhttp_access allow all"'; do
  printf '{"profiles":{"bad":{"credential_names":[],"egress_allowlist":[%s]}}}\n' "$BAD" > "$TMP_ROOT/bad.json"
  if "$PROFILES" plan --profile bad --profiles "$TMP_ROOT/bad.json" --worktree "$TMP_ROOT/worktree" >/dev/null 2>&1; then echo 'FAIL: invalid host accepted' >&2; exit 1; fi
done
if "$PROFILES" plan --profile production --profiles "$TMP_ROOT/profiles.json" --worktree "$TMP_ROOT/worktree" --policy-log "$LOG" >/dev/null 2>&1; then echo 'FAIL: production profile bypassed policy' >&2; exit 1; fi
for BAD in PATH BASH_ENV LD_PRELOAD HTTPS_PROXY DOCKER_HOST; do
  jq -cn --arg name "$BAD" '{profiles:{bad:{credential_names:[$name],egress_allowlist:[]}}}' > "$TMP_ROOT/bad.json"
  if "$PROFILES" plan --profile bad --profiles "$TMP_ROOT/bad.json" --worktree "$TMP_ROOT/worktree" >/dev/null 2>&1; then echo 'FAIL: dangerous env name accepted' >&2; exit 1; fi
done
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NIGHTSHIFT_PRODUCTION_CONFIRMATION_TOKEN=approved "$PROFILES" plan --profile production --profiles "$TMP_ROOT/profiles.json" --worktree "$TMP_ROOT/worktree" --policy-log "$LOG" --confirmation-token approved --confirmed-at "$NOW" | jq -e '.credential_names == ["DEPLOY_TOKEN"]' >/dev/null
printf 'PASS: credential and egress profiles\n'
