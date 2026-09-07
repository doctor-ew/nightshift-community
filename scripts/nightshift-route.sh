#!/usr/bin/env bash
# Pure bounded routing policy: no provider invocation and no filesystem writes.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ROLE=${1:-} RISK=${2:-standard} ATTEMPT=${3:-1} ADV=${4:-false}
case "$RISK" in low|standard|high) ;; *) echo 'invalid risk' >&2; exit 64;; esac
case "$ATTEMPT" in 1|2|3) ;; *) echo 'attempt must be 1..3' >&2; exit 64;; esac
case "$ADV" in true|false) ;; *) exit 64;; esac
START=1
[ "$RISK" != high ] || START=3
if [ "$ROLE" = nightshift-code-fact-extractor ] && [ "$RISK" = low ] && [ "$ADV" = false ]; then START=0; fi
GEAR=$((START + ATTEMPT - 1))
[ "$GEAR" -le 4 ] || GEAR=4
jq -e -c --arg role "$ROLE" --argjson gear "$GEAR" --arg risk "$RISK" \
  --argjson attempt "$ATTEMPT" --arg model "${NIGHTSHIFT_LOCAL_MODEL:-qwen2.5-coder:14b}" '
  if .roles[$role] == null then error("unknown role") else
    (if $gear == 0 then {provider:"local",model:$model} else .roles[$role].gears[($gear|tostring)] end) as $route |
    if ($route.provider != "local" and $route.provider != "codex" and $route.provider != "claude") or ($route.model|type) != "string" or ($route.model|length) == 0
    then error("invalid route") else $route + {gear:$gear,risk:$risk,attempt:$attempt,reason:"deterministic risk/role/attempt policy"} end
  end' "${NIGHTSHIFT_ROUTING_FILE:-$ROOT/routing.json}"
