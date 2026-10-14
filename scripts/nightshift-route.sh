#!/usr/bin/env bash
# Bounded routing policy: local inventory only; no generation or filesystem writes.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
NIGHTSHIFT_ROUTING_FILE=$(python3 "$ROOT/scripts/nightshift-routing-path.py" "$ROOT") || exit 64
export NIGHTSHIFT_ROUTING_FILE
ROLE=${1:-} RISK=${2:-standard} ATTEMPT=${3:-1} ADV=${4:-false} MODE=${5:-auto}
case "$MODE" in auto|explicit) ;; *) exit 64;; esac
case "$RISK" in low|standard|high) ;; *) echo 'invalid risk' >&2; exit 64;; esac
case "$ATTEMPT" in 1|2|3) ;; *) echo 'attempt must be 1..3' >&2; exit 64;; esac
case "$ADV" in true|false) ;; *) exit 64;; esac
START=1
[ "$RISK" != high ] || START=3
if [ "$ROLE" = nightshift-code-fact-extractor ] && [ "$RISK" = low ] && [ "$ADV" = false ]; then START=0; fi
GEAR=$((START + ATTEMPT - 1))
[ "$GEAR" -le 4 ] || GEAR=4
select_route() {
SELECTED=$(jq -e -c --arg role "$ROLE" --argjson gear "$GEAR" --arg risk "$RISK" \
  --argjson attempt "$ATTEMPT" --arg model "${NIGHTSHIFT_LOCAL_MODEL:-qwen2.5-coder:14b}" '
  if .roles[$role] == null then error("unknown role") else
    (if $gear == 0 then {provider:"local",model:(.local.model // $model)} else .roles[$role].gears[($gear|tostring)] end) as $route |
    if ($route.provider != "local" and $route.provider != "codex" and $route.provider != "claude") or ($route.model|type) != "string" or ($route.model|length) == 0
    then error("invalid route") else $route + {gear:$gear,risk:$risk,attempt:$attempt,reason:"deterministic risk/role/attempt policy"} end
  end' "${NIGHTSHIFT_ROUTING_FILE:-$ROOT/routing.json}")
python3 "$ROOT/scripts/nightshift-provider-policy.py" route --routing "${NIGHTSHIFT_ROUTING_FILE:-$ROOT/routing.json}" \
  --role "$ROLE" --gear "$GEAR" --initial "$SELECTED"

}
ROUTE=$(select_route)
if [ "$(jq -r '.gear // -1' <<< "$ROUTE")" = 0 ] && [ "$(jq -r '.provider' <<< "$ROUTE")" = local ]; then
  BACKEND=$(jq -r '.local.backend // "ollama"' "$NIGHTSHIFT_ROUTING_FILE")
  MODEL=$(jq -r '.model' <<< "$ROUTE")
  if ! bash "$ROOT/scripts/nightshift-capability.sh" --local-model "$BACKEND" "$MODEL"; then
    if [ "$MODE" = explicit ]; then echo 'local model unavailable for explicit gear 0' >&2; exit 64; fi
    GEAR=1
    ROUTE=$(select_route)
    ROUTE=$(jq -c '.reason="deterministic risk/role/attempt policy; local model unavailable, promoted to configured gear 1"' <<< "$ROUTE")
  fi
fi
printf '%s\n' "$ROUTE"
