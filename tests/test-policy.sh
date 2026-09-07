#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; POLICY="$ROOT/scripts/nightshift-policy.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-policy.XXXXXX")"; trap 'rm -rf "$TMP_ROOT"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
mkdir -p "$TMP_ROOT/worktree"; LOG="$TMP_ROOT/policy.jsonl"
"$POLICY" check --action worktree-command --worktree "$TMP_ROOT/worktree" --log "$LOG" --command 'bash tests/test.sh' | jq -e '.decision == "allow"' >/dev/null || fail 'normal worktree command was not allowed'
if "$POLICY" check --action permanent-removal --worktree "$TMP_ROOT/worktree" --log "$LOG" --command 'rm file'; then fail 'permanent removal was allowed'; fi
if "$POLICY" check --action history-rewrite --worktree "$TMP_ROOT/worktree" --log "$LOG" --command 'git reset --hard'; then fail 'history rewrite was allowed'; fi
if "$POLICY" check --action production-deploy --worktree "$TMP_ROOT/worktree" --log "$LOG" --command deploy; then fail 'production deploy without token was allowed'; fi
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NIGHTSHIFT_PRODUCTION_CONFIRMATION_TOKEN=approved "$POLICY" check --action production-deploy --worktree "$TMP_ROOT/worktree" --log "$LOG" --command deploy --confirmation-token approved --confirmed-at "$NOW" | jq -e '.decision == "allow"' >/dev/null || fail 'fresh production token was rejected'
[ "$(wc -l < "$LOG" | tr -d ' ')" = 5 ] || fail 'policy decisions were not all logged'
printf 'PASS: policy gateway\n'
