#!/usr/bin/env bash
# Offline contract tests for dp-4t3; no provider binary escapes this fixture PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-dispatch.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/runtime/scripts" "$TMP/bin" "$TMP/out dir"
cp -R "$ROOT/agents" "$ROOT/contracts" "$TMP/runtime/"
cp "$ROOT/routing.json" "$TMP/runtime/routing.json"
cp "$ROOT/scripts/nightshift-agent.sh" "$TMP/runtime/scripts/"
cp "$ROOT/scripts/nightshift-route.sh" "$TMP/runtime/scripts/"
cp "$ROOT/scripts/nightshift-dispatch-bounded.sh" "$TMP/runtime/scripts/"
cp "$ROOT/scripts/nightshift-retry-budget.py" "$TMP/runtime/scripts/"
for helper in "$ROOT/scripts/"*.jq "$ROOT/scripts/nightshift-capability.sh"; do
  [ ! -f "$helper" ] || cp "$helper" "$TMP/runtime/scripts/"
done
cat > "$TMP/bin/claude" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = auth ]; then printf '%s\n' "${MOCK_AUTH:-{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"apiProvider\":\"firstParty\"}}"; exit 0; fi
[ "${NIGHTSHIFT_ROLE_CHILD:-0}" = 1 ] || exit 88
jq -n --args '$ARGS.positional' -- "$@" > "$MOCK_LOG"
[ "${MOCK_EXIT:-0}" = 0 ] || exit "$MOCK_EXIT"
case "${MOCK_MODE:-structured}" in
  malformed) printf 'not json';;
  result) jq -n --arg result "$MOCK_RESPONSE" '{result:$result}';;
  error) jq -n --argjson value "$MOCK_RESPONSE" '{is_error:true,structured_output:$value}';;
  direct) printf '%s\n' "$MOCK_RESPONSE";;
  *) jq -n --argjson value "$MOCK_RESPONSE" '{structured_output:$value}';;
esac
MOCK
cat > "$TMP/bin/codex" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = login ]; then echo 'Logged in using ChatGPT'; exit 0; fi
if [ "${MOCK_MODEL_REJECT:-false}" = true ]; then
  echo 'MCP authentication error: no access token' >&2
  echo 'HTTP 400: model is not supported for this account' >&2
  exit 1
fi
[ "${NIGHTSHIFT_ROLE_CHILD:-0}" = 1 ] || exit 88
if [ "${MOCK_LOCAL_UNAVAILABLE:-false}" = true ] && [[ " $* " == *' --oss '* ]]; then echo 'Ollama connection refused' >&2; exit 1; fi
jq -n --args '$ARGS.positional' -- "$@" > "$MOCK_LOG"
LAST=""; SCHEMA=""
while [ "$#" -gt 0 ]; do
  case "$1" in --output-last-message|-o) shift; LAST="$1";; --output-schema) shift; SCHEMA="$1";; esac
  shift
done
[ "${MOCK_EXIT:-0}" = 0 ] || exit "$MOCK_EXIT"
if [ "${MOCK_MODE:-structured}" = slow ]; then
  sleep 30 &
  tool_pid=$!
  printf '%s\n' "$tool_pid" > "$MOCK_DESC_PID"
  printf '%s\n' "$$" > "$MOCK_PID"
  wait "$tool_pid"
  exit 0
fi
# Provider schema subset excludes composition conditionals unsupported by OpenAI.
jq -e '[.. | objects | keys[] | select(. == "allOf" or . == "if" or . == "then" or . == "else")] | length == 0' "$SCHEMA" >/dev/null || exit 19
printf '%s\n' '{"type":"thread.started","thread_id":"offline"}'
if [ -n "$LAST" ] && [ "${MOCK_MODE:-structured}" != missing ]; then
  if [ "${MOCK_MODE:-structured}" = malformed ]; then printf '{' > "$LAST"
  else printf '%s\n' "$MOCK_RESPONSE" > "$LAST"; fi
fi
MOCK
chmod +x "$TMP/bin/claude" "$TMP/bin/codex"
export PATH="$TMP/bin:$PATH" MOCK_LOG="$TMP/calls.json"
export MOCK_MODE=structured MOCK_EXIT=0
export NIGHTSHIFT_TELEMETRY_DIR="$TMP/telemetry"
INPUT="$TMP/task.txt"; OUTPUT="$TMP/out dir/result.json"
printf '%s\n' 'Task literal $(touch SHOULD_NOT_EXIST) `echo injected` "quoted"' > "$INPUT"
BASE_RESPONSE='{"status":"SUCCESS","reason":"","attempts":1,"artifacts":{"branch":"fixture","diff":"done","provider":"claude","model":"fixture"},"rules_fired":[],"results":{"files_changed":[]}}'
export MOCK_RESPONSE="$BASE_RESPONSE"
PASS=0; FAIL=0; RC=0
check() { local label="$1"; shift; if "$@"; then PASS=$((PASS+1)); else printf 'FAIL: %s\n' "$label" >&2; [ ! -f "$TMP/stderr" ] || tail -10 "$TMP/stderr" >&2; FAIL=$((FAIL+1)); fi; }
json() { jq -e "$1" "$OUTPUT" >/dev/null 2>&1; }
args() { jq -e "$1" "$MOCK_LOG" >/dev/null 2>&1; }
run() { RC=0; bash "$TMP/runtime/scripts/nightshift-agent.sh" "$@" > "$TMP/stdout" 2> "$TMP/stderr" || RC=$?; }
normal() { run nightshift-engineer --gear 1 --in "$INPUT" --out "$OUTPUT" "$@"; }
route() { jq --arg p "$1" '.roles["nightshift-engineer"].gears["1"]={provider:$p,model:"fixture"}' "$TMP/runtime/routing.json" > "$TMP/route.json"; mv "$TMP/route.json" "$TMP/runtime/routing.json"; }
route codex
export MOCK_MODEL_REJECT=true
normal
check 'model rejection outranks unrelated MCP auth noise' json '.status == "FAIL" and (.reason | contains("category=model_unavailable"))'
unset MOCK_MODEL_REJECT
route claude
normal
check 'Claude SUCCESS normalized' json '.status == "SUCCESS" and (has("structured_output")|not)'
check 'terminal telemetry sanitized and complete' jq -e 'keys == ["finished_at","gear","model","pid","provider","role","started_at","status"] and .status == "success" and (.finished_at|length)>0' "$TMP"/telemetry/*.json
check 'Claude inline role selected' args 'index("--agents") != null and index("--agent") != null and index("--json-schema") != null'
check 'Claude transport omits dialect metadata' args '.[index("--json-schema")+1] | fromjson | has("$schema") | not'
check 'Claude transport omits top-level composition' args '.[index("--json-schema")+1] | fromjson | has("allOf") | not'
check 'role body and task injected' args 'join(" ") | contains("Task literal") and contains("Engineer")'
check 'literal input never evaluated' test ! -e SHOULD_NOT_EXIST
NIGHTSHIFT_TELEMETRY_DIR="$INPUT" normal
check 'unwritable telemetry cannot fail dispatch' test "$RC" -eq 0
mkdir "$TMP/outside-telemetry"
ln -s "$TMP/outside-telemetry" "$TMP/telemetry-link"
NIGHTSHIFT_TELEMETRY_DIR="$TMP/telemetry-link/agents" normal
check 'symlink telemetry parent cannot redirect writes' test ! -e "$TMP/outside-telemetry/agents"
check 'symlink telemetry cannot fail dispatch' test "$RC" -eq 0
export MOCK_AUTH='{"loggedIn":true,"authMethod":"api_key","apiProvider":"firstParty"}'
normal
check 'API-backed login rejected in default subscription mode' test "$RC" -ne 0
normal --auth api
check 'explicit API mode accepted' test "$RC" -eq 0
unset MOCK_AUTH
run nightshift-engineer --gear auto --risk high --attempt 3 --in "$INPUT" --out "$OUTPUT"
check 'automatic high-risk bounded gear dispatch' args '.[index("--model")+1] == "opus"'
run nightshift-engineer --gear 0 --risk low --in "$INPUT" --out "$OUTPUT"
check 'gear zero cannot bypass role restriction' test "$RC" -ne 0
MOCK_RESPONSE='{"status":"SUCCESS","reason":"","attempts":1,"artifacts":{"branch":"fixture","diff":"done","provider":"claude","model":"fixture"},"rules_fired":[],"results":{"claims":[]}}'
export MOCK_LOCAL_UNAVAILABLE=true
RC=0
bash "$TMP/runtime/scripts/nightshift-dispatch-bounded.sh" nightshift-code-fact-extractor --risk low --in "$INPUT" --out "$OUTPUT" > "$TMP/stdout" 2> "$TMP/stderr" || RC=$?
check 'missing local service automatically escalates' test "$RC" -eq 0
check 'fallback records second actual attempt' json '.attempts == 2 and .artifacts.provider == "claude"'
check 'fallback preserves sanitized attempt evidence' jq -e 'length == 2 and .[0] == {attempt:1,gear:0,provider:"local",status:"FAIL",reason:"local_unavailable"} and .[1].attempt == 2 and .[1].status == "SUCCESS"' "$OUTPUT.attempts.json"
unset MOCK_LOCAL_UNAVAILABLE
export MOCK_AUTH='{"loggedIn":false}'
RC=0
bash "$TMP/runtime/scripts/nightshift-dispatch-bounded.sh" nightshift-code-fact-extractor --risk standard --in "$INPUT" --out "$OUTPUT" > "$TMP/stdout" 2> "$TMP/stderr" || RC=$?
check 'bounded fallback stops on authentication' json '.status == "FAIL" and .attempts == 1 and (.reason | contains("subscription login"))'
unset MOCK_AUTH
MOCK_RESPONSE="$(printf '%s' "$MOCK_RESPONSE" | jq '.status="FAIL" | .reason="evidence missing"')"
RC=0
bash "$TMP/runtime/scripts/nightshift-dispatch-bounded.sh" nightshift-code-fact-extractor --risk standard --in "$INPUT" --out "$OUTPUT" > "$TMP/stdout" 2> "$TMP/stderr" || RC=$?
check 'bounded fallback never hides semantic failure' json '.status == "FAIL" and .attempts == 1 and .reason == "evidence missing"'
MOCK_RESPONSE="$BASE_RESPONSE"
for provider in codex local; do
  route "$provider"; normal
  check "$provider final message normalized" json '.status == "SUCCESS" and (has("type")|not)'
  check "$provider success exit" test "$RC" -eq 0
  check "$provider read-only and final message flags" args 'index("read-only") != null and index("--output-schema") != null and index("--output-last-message") != null'
  if [ "$provider" = local ]; then check 'OSS flags' args 'index("--oss") != null and index("ollama") != null'; fi
done
route claude
MOCK_MODE=result; normal; check 'Claude result string normalization' json '.status == "SUCCESS"'
MOCK_MODE=direct; normal; check 'direct contract normalization' json '.status == "SUCCESS"'
MOCK_MODE=structured
for mutation in '.attempts=0' '.attempts="one"' '.rules_fired=[1]' '.results.files_changed=[7]' '.artifacts.branch=1' '.extra=true' '.status="UNKNOWN"' '.status="FAIL"|.reason=""'; do
  MOCK_RESPONSE="$(printf '%s' "$BASE_RESPONSE" | jq "$mutation")"; normal
  check "invalid nested contract $mutation" test "$RC" -ne 0
  check "invalid contract receipt $mutation" json '.status == "FAIL" and (.reason|length)>0'
done
MOCK_RESPONSE="$(printf '%s' "$BASE_RESPONSE" | jq '.status="SKIP"|.reason="already done"')"; normal
check 'SKIP valid zero exit' test "$RC" -eq 0
check 'SKIP retained' json '.status == "SKIP"'
MOCK_RESPONSE="$(printf '%s' "$BASE_RESPONSE" | jq '.status="FAIL"|.reason="task failed"')"; normal
check 'agent FAIL nonzero' test "$RC" -ne 0
MOCK_RESPONSE="$BASE_RESPONSE"
for mode in malformed error; do
  MOCK_MODE="$mode"; normal
  check "$mode rejected" test "$RC" -ne 0
  check "$mode replaces stale success" json '.status == "FAIL"'
done
MOCK_MODE=structured; MOCK_EXIT=17; normal
check 'provider exit rejected' test "$RC" -ne 0
check 'provider exit FAIL receipt' json '.status == "FAIL"'
MOCK_EXIT=0
for gear in 0 5 missing; do
  printf 'not-called' > "$MOCK_LOG"; run nightshift-engineer --gear "$gear" --in "$INPUT" --out "$OUTPUT"
  check "invalid gear $gear rejected" test "$RC" -ne 0
  check "invalid gear $gear no launch" grep -qx not-called "$MOCK_LOG"
done
printf 'not-called' > "$MOCK_LOG"; run ../../bad --in "$INPUT" --out "$OUTPUT"
check 'invalid role rejected' test "$RC" -ne 0
check 'invalid role no launch' grep -qx not-called "$MOCK_LOG"
jq '.adversarial.cross_provider=true|.adversarial.routes=[{provider:"codex",model:"review-fixture"},{provider:"local",model:"local-fixture"}]' "$TMP/runtime/routing.json" > "$TMP/route.json"; mv "$TMP/route.json" "$TMP/runtime/routing.json"
normal --adversarial --author-provider claude
check 'cross provider selects Codex' args 'index("exec") != null and index("review-fixture") != null'
check 'selected provider trusted metadata' json '.artifacts.provider == "codex" and .artifacts.model == "review-fixture"'
normal --adversarial --author-provider codex
check 'different primary retained' args 'index("--agents") != null'
normal --adversarial
check 'missing author rejected' test "$RC" -ne 0
jq '.adversarial.routes=[]' "$TMP/runtime/routing.json" > "$TMP/route.json"; mv "$TMP/route.json" "$TMP/runtime/routing.json"
normal --adversarial --author-provider claude
check 'no alternate fails closed' test "$RC" -ne 0
jq '.adversarial.cross_provider=false' "$TMP/runtime/routing.json" > "$TMP/route.json"; mv "$TMP/route.json" "$TMP/runtime/routing.json"
normal --adversarial --author-provider claude
check 'disabled cross provider retains primary' test "$RC" -eq 0
for role in nightshift-architect nightshift-code-fact-extractor nightshift-run-all-tests nightshift-spec-writer; do
  case "$role" in
    *architect) result='{"files_changed":[]}' ;;
    *extractor) result='{"claims":[{"claim":"example","status":"VERIFIED","file":"a.sh","line":1,"inspected_files":["a.sh"]}]}' ;;
    *tests) result='{"passed":2,"failed":0}' ;;
    *writer) result='{"spec_path":"docs/example/SPEC.md"}' ;;
  esac
  MOCK_RESPONSE="$(printf '%s' "$BASE_RESPONSE" | jq --argjson r "$result" '.results=$r')"
  run "$role" --gear 1 --in "$INPUT" --out "$OUTPUT"
  check "$role valid output" test "$RC" -eq 0
  check "$role normalized" json '.status == "SUCCESS"'
  MOCK_RESPONSE="$(printf '%s' "$BASE_RESPONSE" | jq '.results={}')"
  run "$role" --gear 1 --in "$INPUT" --out "$OUTPUT"
  check "$role missing result rejected" test "$RC" -ne 0
done
MOCK_RESPONSE="$BASE_RESPONSE"
# AC7 cancellation must promptly cancel the provider and replace stale success.
route codex; MOCK_MODE=slow
export MOCK_PID="$TMP/provider.pid" MOCK_DESC_PID="$TMP/tool.pid"
printf '%s\n' "$BASE_RESPONSE" > "$OUTPUT"
bash "$TMP/runtime/scripts/nightshift-agent.sh" nightshift-engineer --gear 1 --in "$INPUT" --out "$OUTPUT" > "$TMP/stdout" 2> "$TMP/stderr" &
dispatch_pid=$!
for _ in $(seq 1 40); do [ ! -f "$MOCK_PID" ] || break; sleep 0.05; done
check 'slow provider started' test -f "$MOCK_PID"
check 'running telemetry precedes provider completion' jq -e '.status == "running" and .finished_at == ""' "$TMP"/telemetry/dispatch-"$dispatch_pid"-*.json
kill -TERM "$dispatch_pid" 2>/dev/null || true
for _ in $(seq 1 40); do kill -0 "$dispatch_pid" 2>/dev/null || break; sleep 0.05; done
if kill -0 "$dispatch_pid" 2>/dev/null; then check 'dispatcher interruption bounded' false; kill -KILL "$dispatch_pid" 2>/dev/null || true
else check 'dispatcher interruption bounded' true; fi
wait "$dispatch_pid" 2>/dev/null || true
check 'interrupted telemetry finalized' jq -e '.status == "interrupted" and (.finished_at|length)>0' "$TMP"/telemetry/dispatch-"$dispatch_pid"-*.json
check 'interruption replaces stale success' json '.status == "FAIL"'
if [ -f "$MOCK_PID" ]; then
  provider_pid="$(cat "$MOCK_PID")"
  if kill -0 "$provider_pid" 2>/dev/null; then check 'provider cancelled' false; kill -KILL "$provider_pid" 2>/dev/null || true
  else check 'provider cancelled' true; fi
fi
if [ -f "$MOCK_DESC_PID" ]; then
  descendant_pid="$(cat "$MOCK_DESC_PID")"
  descendant_state="$(ps -o stat= -p "$descendant_pid" 2>/dev/null || true)"
  case "$descendant_state" in
    ''|Z*) check 'provider descendants cancelled' true;;
    *) check 'provider descendants cancelled' false; kill -KILL "$descendant_pid" 2>/dev/null || true;;
  esac
else check 'descendant fixture created' false; fi
MOCK_MODE=structured
# Run installed copies from an unrelated directory with all destinations private.
for mode in copy symlink; do
  destination="$TMP/install-$mode"
  if bash "$ROOT/install.sh" "--$mode" --runtime local --nightshift-target "$destination/runtime" --codex-target "$destination/codex" --target "$destination/claude" --bin-target "$destination/bin" > "$TMP/install.log" 2>&1; then
    check "$mode contracts installed" test -f "$destination/runtime/contracts/nightshift-spec-writer.schema.json"
    check "$mode validator installed" test -f "$destination/runtime/scripts/nightshift-contract.jq"
    RC=0
    (cd "$TMP" && bash "$destination/runtime/scripts/nightshift-agent.sh" nightshift-engineer --gear 1 --in "$INPUT" --out "$OUTPUT") > "$TMP/stdout" 2> "$TMP/stderr" || RC=$?
    check "$mode installed dispatch" test "$RC" -eq 0
    check "$mode installed normalized" json '.status == "SUCCESS"'
  else
    check "$mode installation" false
  fi
done
printf 'Dispatch assertions: %s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
