#!/usr/bin/env bash
# Transport-only fallback for product extraction. Semantic failures require repair.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ROLE=${1:-}; [ "$#" -eq 0 ] || shift
OUTPUT='' EXPECT_OUTPUT=false RISK=${NIGHTSHIFT_RISK:-standard} EXPECT_RISK=false ADV=false
for arg in "$@"; do
  if [ "$EXPECT_RISK" = true ]; then RISK=$arg; EXPECT_RISK=false; fi
  if [ "$EXPECT_OUTPUT" = true ]; then OUTPUT=$arg; EXPECT_OUTPUT=false; fi
  [ "$arg" != --out ] || EXPECT_OUTPUT=true
  [ "$arg" != --risk ] || EXPECT_RISK=true
  [ "$arg" != --adversarial ] || ADV=true
  case "$arg" in --attempt|--gear) echo 'bounded dispatcher owns gear and attempt' >&2; exit 64;; esac
done
[ "$ROLE" = nightshift-code-fact-extractor ] && [ -n "$OUTPUT" ] || exit 64
HISTORY='[]' JOURNAL_TMP=''
trap '[ -z "$JOURNAL_TMP" ] || rm -f -- "$JOURNAL_TMP"' EXIT
publish_history() {
  JOURNAL_TMP=$(mktemp "$(dirname "$OUTPUT")/.nightshift-attempts.XXXXXX")
  printf '%s\n' "$HISTORY" > "$JOURNAL_TMP"
  mv -f -- "$JOURNAL_TMP" "$OUTPUT.attempts.json"
  JOURNAL_TMP=''
}
publish_history
for attempt in 1 2 3; do
  result=0
  bash "$ROOT/scripts/nightshift-agent.sh" "$ROLE" --gear auto --attempt "$attempt" "$@" || result=$?
  gear=$(bash "$ROOT/scripts/nightshift-route.sh" "$ROLE" "$RISK" "$attempt" "$ADV" | jq '.gear') || gear=null
  # Never persist arbitrary model reasons or transport output in the sidecar.
  entry=$(jq -c --argjson attempt "$attempt" --argjson gear "$gear" '
    {attempt:$attempt,gear:$gear,
     provider:(if (.artifacts.provider | IN("local","codex","claude")) then .artifacts.provider else "unknown" end),
     status:(if (.status | IN("SUCCESS","FAIL","SKIP")) then .status else "FAIL" end),
     reason:(if .status == "SUCCESS" then "success"
       elif .status == "SKIP" then "skipped"
       elif (.reason | contains("category=local_unavailable)")) then "local_unavailable"
       elif (.reason | contains("category=capacity)")) then "capacity"
       elif (.reason | contains("exit=127 category=unknown)")) then "runtime_missing"
       elif (.rules_fired | index("dispatcher_failure")) then "dispatcher_failure"
       else "semantic_failure" end)}' "$OUTPUT") || exit 1
  HISTORY=$(jq -cn --argjson history "$HISTORY" --argjson entry "$entry" '$history + [$entry]')
  publish_history
  [ "$result" -ne 0 ] || exit 0
  # Only infrastructure availability failures can transparently move provider.
  # Authentication, schema, policy and semantic FAIL are terminal here.
  jq -e '.rules_fired | index("dispatcher_failure") != null' "$OUTPUT" >/dev/null 2>&1 || exit "$result"
  reason=$(jq -r '.reason' "$OUTPUT")
  case "$reason" in
    *'category=capacity)'*|*'category=local_unavailable)'*|*'exit=127 category=unknown)'*) ;;
    *) exit "$result";;
  esac
done
exit 1
