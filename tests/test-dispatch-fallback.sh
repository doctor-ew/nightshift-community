#!/usr/bin/env bash
# Offline route exhaustion regression; no provider is launched.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-fallback.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/scripts"
cp "$ROOT/scripts/nightshift-dispatch-bounded.sh" "$TMP/scripts/"
cat > "$TMP/scripts/nightshift-agent.sh" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
attempt=0 output=''
while [ "$#" -gt 0 ]; do
  case "$1" in --attempt) attempt=$2; shift 2;; --out) output=$2; shift 2;; *) shift;; esac
done
status=FAIL reason='provider unavailable (category=capacity)'
if [ "$attempt" -eq 4 ] && [ "${FAIL_FINAL:-false}" != true ]; then status=SUCCESS; reason=''; fi
jq -n --arg status "$status" --arg reason "$reason" --argjson attempt "$attempt" '{status:$status,reason:$reason,artifacts:{provider:"claude"},rules_fired:(["route_gear:"+($attempt|tostring)]+if $status=="FAIL" then ["dispatcher_failure"] else [] end)}' > "$output"
[ "$status" = SUCCESS ]
STUB
bash "$TMP/scripts/nightshift-dispatch-bounded.sh" nightshift-code-fact-extractor --out "$TMP/result.json"
jq -e 'length==4 and .[3].status=="SUCCESS"' "$TMP/result.json.attempts.json" >/dev/null
if FAIL_FINAL=true bash "$TMP/scripts/nightshift-dispatch-bounded.sh" nightshift-code-fact-extractor --out "$TMP/result.json"; then
  echo 'FAIL: exhausted route space passed' >&2; exit 1
fi
jq -e 'length==4 and .[3].status=="FAIL"' "$TMP/result.json.attempts.json" >/dev/null
printf 'PASS: fallback reaches fourth route and retains actual route exhaustion\n'
