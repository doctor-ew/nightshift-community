#!/usr/bin/env bash
set -euo pipefail
# These fixtures inspect raw provider/admission output.
export NIGHTSHIFT_OUTPUT=verbose

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FACTORY="${REPO_DIR}/scripts/nightshift-factory.sh"
export NIGHTSHIFT_SYNC_CHECK=off
export NIGHTSHIFT_DASHBOARD=off
cd "$REPO_DIR"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-factory-auth.XXXXXX")"
TMP_ROOT="$(cd "$TMP_ROOT" && pwd -P)"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_contains() { case "$1" in *"$2"*) ;; *) fail "expected '$2' in '$1'" ;; esac; }

mkdir -p "$TMP_ROOT/bin" "$TMP_ROOT/home/.nightshift"
cp "$REPO_DIR/nightshift.toml" "$REPO_DIR/routing.json" "$TMP_ROOT/"
cat > "$TMP_ROOT/bin/codex" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "login" ] && [ "${2:-}" = "status" ]; then
  printf '%s\n' "${CODEX_LOGIN_STATUS:-Logged in using ChatGPT}"
  exit 0
fi
printf 'OPENAI_API_KEY=%s\n' "${OPENAI_API_KEY:+present}"
printf 'ANTHROPIC_API_KEY=%s\n' "${ANTHROPIC_API_KEY:+present}"
printf 'ARGS=%s\n' "$*"
printf 'EXECUTION_MODE=%s/%s\n' "${AUTONOMOUS:-}" "${NIGHTSHIFT_FACTORY_MODE:-}"
printf 'ROUTING_FILE=%s\n' "${NIGHTSHIFT_ROUTING_FILE:-}"
exit "${CODEX_EXIT_STATUS:-0}"
EOF
chmod +x "$TMP_ROOT/bin/codex"

mkdir "$TMP_ROOT/invalid-config"
cp "$REPO_DIR/nightshift.toml" "$TMP_ROOT/invalid-config/.nightshift.toml"
cp "$REPO_DIR/routing.json" "$TMP_ROOT/invalid-config/routing.json"
sed -i.bak 's/allow_heuristic_production_target = false/allow_heuristic_production_target = true/' "$TMP_ROOT/invalid-config/.nightshift.toml"
if invalid=$(PATH="$TMP_ROOT/bin:$PATH" "$FACTORY" gh:1 --project "$TMP_ROOT/invalid-config" --branch none 2>&1); then fail 'invalid complete configuration launched'; fi
case "$invalid" in *'ARGS='*) fail 'invalid configuration invoked provider';; esac
configured=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --project "$TMP_ROOT" --branch none 2>&1)
assert_contains "$configured" "ROUTING_FILE=$TMP_ROOT/routing.json"

subscription=$(PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" OPENAI_API_KEY=secret "$FACTORY" gh:1 --branch none 2>&1)
assert_contains "$subscription" 'authentication: ChatGPT subscription'
assert_contains "$subscription" 'EXECUTION_MODE=true/true'
assert_contains "$subscription" 'OPENAI_API_KEY='
assert_contains "$subscription" 'inner Nightshift factory worker'
assert_contains "$subscription" 'Do not run the terminal launcher'
assert_contains "$subscription" 'Authorized role dispatch is different'
assert_contains "$subscription" 'Do not launch Codex directly'
case "$subscription" in *'do not start another Codex process'*) fail 'blanket verifier prohibition returned';; esac
if NIGHTSHIFT_ROLE_CHILD=1 "$FACTORY" --help >/dev/null 2>&1; then fail 'role child launched factory'; fi
if NIGHTSHIFT_ROLE_CHILD=1 bash "$REPO_DIR/scripts/nightshift-agent.sh" >/dev/null 2>&1; then fail 'role child nested dispatcher'; fi
assert_contains "$subscription" 'Do not deploy, merge a PR'
assert_contains "$subscription" 'Follow ticket dependencies in order'
set +e
capacity=$(PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" OPENAI_API_KEY=secret CODEX_EXIT_STATUS=75 "$FACTORY" gh:1 --branch none 2>&1)
capacity_status=$?
set -e
[ "$capacity_status" -eq 75 ] || fail 'provider failure was not preserved'
case "$capacity" in *'API_KEY=present'*|*'authentication: API key billing'*) fail 'provider failure enabled paid fallback';; esac

printf 'NIGHTSHIFT_AUTH=api\n' > "$TMP_ROOT/home/.nightshift/config"
saved_api=$(PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" OPENAI_API_KEY=secret ANTHROPIC_API_KEY=secret "$FACTORY" gh:1 --branch none 2>&1)
assert_contains "$saved_api" 'saved API preference ignored'
assert_contains "$saved_api" 'forced_login_method="chatgpt"'
case "$saved_api" in *'API_KEY=present'*) fail 'default leaked billing credentials';; esac
api=$(PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" OPENAI_API_KEY=secret "$FACTORY" gh:1 --auth api --branch none 2>&1)
assert_contains "$api" 'authentication: API key billing'
assert_contains "$api" 'OPENAI_API_KEY=present'

if PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CODEX_LOGIN_STATUS='Logged in using an API key' "$FACTORY" gh:1 --auth subscription --branch none >/dev/null 2>&1; then
  fail 'subscription mode accepted an API-key login'
fi

interrupted=$(PATH="$TMP_ROOT/bin:$PATH" HOME="$TMP_ROOT/home" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CODEX_EXIT_STATUS=143 "$FACTORY" gh:1 --auth api --branch none 2>&1 || true)
assert_contains "$interrupted" 'Codex received SIGTERM'

printf 'PASS: nightshift factory authentication policy\n'

cat > "$TMP_ROOT/bin/claude" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = auth ]; then
  printf '%s\n' "${CLAUDE_LOGIN_STATUS:-{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"apiProvider\":\"firstParty\"}}"
  exit 0
fi
sleep "${CLAUDE_TEST_DELAY:-0}"
printf 'CLAUDE_CWD=%s\n' "$PWD"
printf 'ANTHROPIC_API_KEY=%s\n' "${ANTHROPIC_API_KEY:+present}"
printf 'CLAUDE_ARGS=%s\n' "$*"
exit "${CLAUDE_EXIT_STATUS:-0}"
EOF
chmod +x "$TMP_ROOT/bin/claude"
if PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CLAUDE_LOGIN_STATUS='{"loggedIn":true,"authMethod":"api_key","apiProvider":"firstParty"}' "$FACTORY" gh:1 --provider claude --branch none >/dev/null 2>&1; then
  fail 'Claude API-key login accepted without per-run opt-in'
fi
for auth_status in '{}' 'not-json' '{"loggedIn":false}' '{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"bedrock"}'; do
  if PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CLAUDE_LOGIN_STATUS="$auth_status" "$FACTORY" gh:1 --provider claude --branch none >/dev/null 2>&1; then
    fail 'unverified Claude login accepted'
  fi
done
claude_api=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" ANTHROPIC_API_KEY=secret "$FACTORY" gh:1 --provider claude --auth api --branch none 2>&1)
assert_contains "$claude_api" 'ANTHROPIC_API_KEY=present'
assert_contains "$claude_api" '/nightshift-eng gh:1 --auth api'
assert_contains "$claude_api" 'Publication authorization: push=false, pr=false'
assert_contains "$claude_api" 'an absent remote is not a blocker'
git -C "$TMP_ROOT" init -q -b main
if blocked=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --project "$TMP_ROOT" --branch auto 2>&1); then fail 'unborn repository launched a model'; fi
assert_contains "$blocked" 'BASE_MISSING'
case "$blocked" in *'ARGS='*) fail 'baseline check ran after provider execution';; esac
git -C "$TMP_ROOT" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m baseline
# Resume admission now requires real state; this remains an auth/argv test.
mkdir -p "$TMP_ROOT/.nightshift"
printf '%s\n' '{"tickets":["gh:1"],"statuses":{"gh:1":{"status":"pending"}}}' > "$TMP_ROOT/.nightshift/batch-20260906-1323.json"
cp "$REPO_DIR/nightshift.toml" "$TMP_ROOT/.nightshift.toml"
claude_output=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" ANTHROPIC_API_KEY=secret "$FACTORY" batch --resume batch-20260906-1323.json --provider claude --model sonnet --auth subscription --project "$TMP_ROOT" --push --pr 2>&1)
assert_contains "$claude_output" "CLAUDE_CWD=$(cd "$TMP_ROOT" && pwd)"
assert_contains "$claude_output" '--print --output-format stream-json --verbose --disallowedTools Agent,Task --dangerously-skip-permissions --model sonnet'
assert_contains "$claude_output" '/nightshift-batch --resume batch-20260906-1323.json --branch auto --push --pr'
case "$claude_output" in *'ANTHROPIC_API_KEY=present'*|*'OPENAI_API_KEY='*) fail 'Claude dispatch leaked API key or invoked Codex';; esac
set +e
PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CLAUDE_EXIT_STATUS=42 "$FACTORY" gh:1 --provider claude --branch none >/dev/null 2>&1
claude_status=$?
set -e
[ "$claude_status" -eq 42 ] || fail 'Claude exit status was not preserved'
printf 'PASS: Claude factory dispatch, resume, model, credentials, and exit status\n'

# Explicit project policy dominates runtime selection and inherited CLI overrides.
policy_project="$TMP_ROOT/claude-policy"
mkdir -p "$policy_project"
cp "$REPO_DIR/nightshift.toml" "$policy_project/.nightshift.toml"
cp "$REPO_DIR/routing.json" "$policy_project/routing.json"
python3 - "$policy_project/.nightshift.toml" <<'PYMODE'
from pathlib import Path
import sys
p=Path(sys.argv[1]);p.write_text(p.read_text().replace('[providers]', '[providers]\npolicy = "claude-only"'))
PYMODE
policy_output=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --project "$policy_project" --branch none 2>&1)
assert_contains "$policy_output" 'CLAUDE_ARGS='
assert_contains "$policy_output" 'Provider policy: claude-only'
assert_contains "$policy_output" 'permits a fresh isolated Claude reviewer session'
assert_contains "$policy_output" 'Current invocation provider policy supersedes historical reviewer-provider requests'
assert_contains "$policy_output" 'operator-owned delivery check remains pending manual acceptance'
case "$policy_output" in *'does not permit same-provider self-approval'*) fail 'contradictory reviewer policy';; esac
for selected in codex local; do
  if blocked=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --project "$policy_project" --branch none --provider "$selected" --model fixture --provider-policy standard 2>&1); then
    fail 'explicit runtime bypassed Claude-only project policy'
  fi
  case "$blocked" in *'ARGS='*) fail 'disallowed runtime was launched';; esac
done
policy_cli=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --project "$TMP_ROOT" --branch none --provider-policy claude-only 2>&1)
assert_contains "$policy_cli" 'CLAUDE_ARGS='
echo 'PASS: Claude-only factory policy and explicit runtime rejection'

# The individual stage receives only options its parser supports.
args_output=$(PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" "$FACTORY" gh:1 --provider claude --project "$TMP_ROOT" --base main --push --pr 2>&1)
assert_contains "$args_output" '/nightshift-eng gh:1 --base main'
assert_contains "$args_output" 'Publication authorization: push=true, pr=true'
assert_contains "$args_output" '--disallowedTools Agent,Task'
case "$args_output" in *'/nightshift-eng gh:1 --branch'*|*'/nightshift-eng gh:1 --base main --push'*) fail 'factory flags leaked into stage parser';; esac
python3 - "$TMP_ROOT/.nightshift/agents" <<'PYRECORD'
import json, pathlib, sys
records = [json.loads(p.read_text()) for p in pathlib.Path(sys.argv[1]).glob('factory-*.json')]
assert records and all(r['role'] == 'nightshift-factory' for r in records)
assert any(r['provider'] == 'claude' and r['finished_at'] for r in records)
assert all(r['status'] != 'running' for r in records)
PYRECORD
printf 'PASS: engineering arguments, native delegation restriction, factory lifecycle\n'

# Observe startup before the stub provider returns, then verify terminal state.
PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_HOME="$TMP_ROOT/home/.nightshift" CLAUDE_TEST_DELAY=3 "$FACTORY" gh:1 --provider claude --project "$TMP_ROOT" --branch none > "$TMP_ROOT/live.log" 2>&1 &
live_pid=$!
python3 - "$TMP_ROOT/.nightshift/agents" <<'PYLIVE'
import json, pathlib, sys, time
folder=pathlib.Path(sys.argv[1])
for attempt in range(100):
    records=[json.loads(p.read_text()) for p in folder.glob('factory-*.json')]
    if any(r['status']=='running' and not r['finished_at'] for r in records):
        break
    time.sleep(0.1)
else:
    raise AssertionError('factory was invisible while provider was running')
PYLIVE
wait "$live_pid"
printf 'PASS: factory visible before first role dispatch\n'
