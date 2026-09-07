#!/usr/bin/env bash
# Validate profiles without reading or emitting secret values.
set -euo pipefail
usage() { echo 'usage: nightshift-credentials.sh plan --profile NAME [--profiles FILE] --worktree DIR [--policy-log FILE --confirmation-token TOKEN --confirmed-at TIME]' >&2; exit 64; }
[ "${1:-}" = plan ] || usage; shift
PROFILE="${NIGHTSHIFT_CREDENTIAL_PROFILE:-offline}"; FILE="${NIGHTSHIFT_PROFILES_FILE:-}"; WORKTREE=""; LOG=""; TOKEN=""; AT=""
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || usage
  case "$1" in
    --profile) PROFILE="$2";; --profiles) FILE="$2";; --worktree) WORKTREE="$2";; --policy-log) LOG="$2";;
    --confirmation-token) TOKEN="$2";; --confirmed-at) AT="$2";; *) usage;;
  esac
  shift 2
done
[ -d "$WORKTREE" ] || usage
if [ -z "$FILE" ]; then
  [ "$PROFILE" = offline ] || { echo 'configured profiles file required for non-offline profile' >&2; exit 78; }
  PLAN='{"credential_names":[],"egress_allowlist":[],"production":false}'
else
  PLAN=$(jq -ce --arg profile "$PROFILE" '.profiles[$profile] | select(type == "object") |
    select((keys - ["credential_names","egress_allowlist","production"]) == []) |
    select(.credential_names | type == "array") | select(.egress_allowlist | type == "array") |
    select(all(.credential_names[]; type == "string" and test("^[A-Z_][A-Z0-9_]*$"))) |
    select(all(.credential_names[]; test("^(PATH|HOME|ENV|BASH_ENV|SHELLOPTS|LD_.*|DYLD_.*|DOCKER_.*|CONTAINER_.*|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY)$") | not)) |
    select(all(.egress_allowlist[]; type == "string" and length < 254 and test("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\\.[a-z]{2,}$") and (endswith(".invalid") | not))) |
    select((.production // false) | type == "boolean") |
    .production = (.production // false)' "$FILE") || { echo 'invalid or missing credential profile' >&2; exit 78; }
fi
if [ "$(jq -r '.production' <<< "$PLAN")" = true ] || [ "$PROFILE" = production ]; then
  [ -n "$LOG" ] || { echo 'production profile requires policy log and fresh confirmation' >&2; exit 78; }
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  bash "$SCRIPT_DIR/nightshift-policy.sh" check --action production-deploy --worktree "$WORKTREE" --log "$LOG" --command 'release production credential profile' --confirmation-token "$TOKEN" --confirmed-at "$AT" >/dev/null
fi
jq -c --arg profile "$PROFILE" '. + {profile:$profile,inject_values:false}' <<< "$PLAN"
