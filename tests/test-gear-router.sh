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
route nightshift-engineer low 4 false | jq -e '.gear == 4 and .attempt == 4' >/dev/null
route nightshift-engineer low 12 false | jq -e '.gear == 4 and .attempt == 12' >/dev/null
for attempt in 0 -1 1.5 nope; do
  if route nightshift-engineer low "$attempt" false; then exit 1; fi
done
if route nightshift-engineer mystery 1 false; then exit 1; fi
printf 'gear router: extended assertions passed\n'
