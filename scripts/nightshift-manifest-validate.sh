#!/usr/bin/env bash
# Validate the portable Nightshift manifest without a language runtime beyond bash + jq.
set -euo pipefail

PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [ "${1:-}" = "--project" ]; then PROJECT="${2:?--project requires a directory}"; shift 2; fi
[ "$#" -eq 0 ] || { printf '%s\n' '{"status":"failed","code":"MANIFEST_USAGE","message":"usage: nightshift-manifest-validate.sh [--project DIR]"}'; exit 64; }
MANIFEST="$(bash "$(dirname "$0")/nightshift-manifest-path.sh" --project "$PROJECT")"
fail() { jq -cn --arg code "$1" --arg message "$2" '{status:"failed",code:$code,message:$message}'; exit 1; }
[ -f "$MANIFEST" ] || fail MANIFEST_MISSING "nightshift.toml is required"

# This intentionally accepts the small, documented scalar subset used by the manifest.
value() { awk -F= -v section="$1" -v key="$2" '
  $0 ~ "^\\[" section "\\]$" { in_section=1; next }
  /^\[/ { in_section=0 }
  in_section && $1 ~ "^[[:space:]]*" key "[[:space:]]*$" { v=$2; sub(/^[[:space:]]*/,"",v); sub(/[[:space:]]*(#.*)?$/,"",v); gsub(/^"|"$/, "", v); print v; exit }
' "$MANIFEST"; }
required_string() { local v; v="$(value "$1" "$2")"; [ -n "$v" ] || fail MANIFEST_INVALID "[$1].$2 must be a non-empty string"; printf '%s' "$v"; }
required_bool() { local v; v="$(value "$1" "$2")"; [ "$v" = true ] || [ "$v" = false ] || fail MANIFEST_INVALID "[$1].$2 must be true or false"; }
required_budget() { local v; v="$(value repair_budgets "$1")"; [[ "$v" =~ ^[1-9][0-9]*$ ]] || fail MANIFEST_INVALID "[repair_budgets].$1 must be a positive integer"; }

provider="$(required_string ticket_source provider)"
[ -f "${PROJECT}/$(required_string providers routing_file)" ] || fail MANIFEST_INVALID "[providers].routing_file must name an existing file"
production_name="$(required_string deployments.production name)"
[ "$production_name" = production ] || fail MANIFEST_INVALID "[deployments.production].name must be exactly production"
production_url="$(required_string deployments.production url)"
[[ "$production_url" =~ ^https:// ]] || fail MANIFEST_INVALID "[deployments.production].url must be an explicit HTTPS URL"
required_string deployments.production health_path >/dev/null
required_bool policy require_production_confirmation
required_bool policy require_removal_confirmation
[ "$(value policy allow_heuristic_production_target)" = false ] || fail MANIFEST_INVALID "[policy].allow_heuristic_production_target must be false"
for gate in implement review drift qa; do required_budget "$gate"; done
jq -cn --arg provider "$provider" --arg url "$production_url" '{status:"ok",ticket_source:$provider,production_url:$url}'
