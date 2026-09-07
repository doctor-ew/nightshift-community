#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
parse() { python3 "$ROOT/scripts/nightshift-stage-args.py" "$1"; }
parse 'bd:ticket --auth api --base branch' | jq -e '.auth == "api" and .arguments == "bd:ticket --base branch"' >/dev/null
STAGE_AUTH=api parse 'bd:ticket' | jq -e '.auth == "subscription"' >/dev/null
parse '"bd:a,bd:b" --auth subscription' | jq -e '.argv == ["bd:a,bd:b"]' >/dev/null
if parse 'bd:a --auth'; then exit 1; fi
if parse 'bd:a --auth api --auth api'; then exit 1; fi
if parse 'bd:a --auth other'; then exit 1; fi
printf 'PASS: literal stage auth parsing and inherited auth rejection\n'
