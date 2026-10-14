#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-gear-router.XXXXXX")
trap 'rm -rf "$FIXTURE"' EXIT
mkdir "$FIXTURE/bin"
for TOOL in bash dirname python3 jq git rm; do ln -s "$(command -v "$TOOL")" "$FIXTURE/bin/$TOOL"; done
cat > "$FIXTURE/bin/ollama" <<'SH'
#!/bin/bash
[[ "$*" == list ]] || exit 99
printf 'NAME ID SIZE MODIFIED\nqwen2.5-coder:14b fixture 9GB now\n'
SH
cat > "$FIXTURE/bin/codex" <<'SH'
#!/bin/bash
exit 99
SH
chmod +x "$FIXTURE/bin/ollama" "$FIXTURE/bin/codex"
export PATH="$FIXTURE/bin" NIGHTSHIFT_HOME="$FIXTURE" NIGHTSHIFT_PROJECT_DIR="$FIXTURE"
export NIGHTSHIFT_ROUTING_FILE="$ROOT/routing.json"
route() { bash "$ROOT/scripts/nightshift-route.sh" "$@"; }
route nightshift-code-fact-extractor low 1 false | jq -e '.gear == 0 and .provider == "local"' >/dev/null
route nightshift-engineer low 1 false | jq -e '.gear == 1' >/dev/null
route nightshift-engineer high 3 false | jq -e '.gear == 4' >/dev/null
route nightshift-code-fact-extractor low 1 true | jq -e '.gear == 1' >/dev/null
route nightshift-code-fact-extractor low 2 false | jq -e '.gear == 1' >/dev/null
if route nightshift-engineer low 4 false; then exit 1; fi
if route nightshift-engineer mystery 1 false; then exit 1; fi
printf 'gear router: seven assertions passed\n'
