#!/usr/bin/env bash
set -euo pipefail
PROJECT="${PWD}"
if [ "${1:-}" = --project ]; then PROJECT="${2:?directory required}"; shift 2; fi
[ "$#" -eq 0 ] || exit 64
exec python3 "$(dirname "$0")/nightshift-project-context.py" --project "$PROJECT" --manifest-only
