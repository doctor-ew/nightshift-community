#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
route() { bash "$ROOT/scripts/nightshift-route.sh" "$@"; }
route nightshift-code-fact-extractor low 1 false | jq -e '.gear == 0 and .provider == "local"' >/dev/null
route nightshift-engineer low 1 false | jq -e '.gear == 1' >/dev/null
route nightshift-engineer high 3 false | jq -e '.gear == 4' >/dev/null
route nightshift-code-fact-extractor low 1 true | jq -e '.gear == 1' >/dev/null
route nightshift-code-fact-extractor low 2 false | jq -e '.gear == 1' >/dev/null
if route nightshift-engineer low 4 false; then exit 1; fi
if route nightshift-engineer mystery 1 false; then exit 1; fi
printf 'gear router: seven assertions passed\n'
