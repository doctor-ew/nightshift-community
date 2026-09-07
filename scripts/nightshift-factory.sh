#!/usr/bin/env bash
# nightshift-factory.sh — one-call, agent-agnostic Nightshift entrypoint for a ticket.
#
# Usage:
#   nightshift <ticket-ref> [--branch auto|NAME|none] [--push] [--pr] [runtime options]
#   nightshift batch <tickets-or-query> [--push] [runtime options]
#
# Runs Codex in the target project and invokes the installed nightshift skill.
# Factory sessions bypass CLI approval prompts; Nightshift retains semantic deletion and
# production-deploy gates in its own policy until the policy gateway lands.

set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
  LINK_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
  SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
  case "$SCRIPT_PATH" in /*) ;; *) SCRIPT_PATH="$LINK_DIR/$SCRIPT_PATH" ;; esac
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ "${1:-}" = --sync ]; then
  shift
  exec python3 "$SCRIPT_DIR/nightshift-update.py" --project "$SOURCE_DIR" --apply --heal "$@"
fi
if [ "${NIGHTSHIFT_UPDATE_GUARD:-}" != 1 ] && [ "${1:-}" != sync ]; then
  case "${1:-}" in
    version|setup|dashboard|--help|-h|"") ;;
    *) exec python3 "$SCRIPT_DIR/nightshift-update.py" --project "$SOURCE_DIR" --run "$@" ;;
  esac
fi
if [ "${1:-}" = sync ]; then
  shift
  exec python3 "$SCRIPT_DIR/nightshift-update.py" --project "$SOURCE_DIR" "$@"
fi
if [ "${1:-}" = "version" ]; then shift; exec "$SCRIPT_DIR/nightshift-version.sh" --project "$SOURCE_DIR" "$@"; fi
if [ "${1:-}" = "setup" ]; then shift; exec bash "$SCRIPT_DIR/nightshift-setup.sh" "$@"; fi
if [ "${1:-}" = "dashboard" ]; then shift; exec bash "$SCRIPT_DIR/nightshift-dashboard.sh" --serve "$@"; fi

PROJECT="$(pwd)"
PROVIDER=""
MODEL=""
DASHBOARD="${NIGHTSHIFT_DASHBOARD:-}"
DASHBOARD_BROWSER="${NIGHTSHIFT_DASHBOARD_BROWSER:-}"
REF=""
MODE="eng"
BRANCH="auto"
PUSH="false"
OPEN_PR="false"
BATCH_ARGS=()
AUTH_MODE=""
AUTH_EXPLICIT=false
NIGHTSHIFT_HOME_DIR="${NIGHTSHIFT_HOME:-${HOME}/.nightshift}"
AUTH_CONFIG="${NIGHTSHIFT_HOME_DIR}/config"

usage() {
  cat <<'EOF'
Usage: nightshift <ticket-ref> [options]
       nightshift batch <tickets-or-query> [options]
       nightshift setup [--project DIR]
       nightshift dashboard [--project DIR] [--port PORT]

One autonomous Nightshift run. Examples:
  nightshift gh:123
  nightshift jira:APP-42 --project /path/to/app
  nightshift gh:123 --branch auto --push --pr
  nightshift batch "MVP-1,MVP-2" --push
  nightshift gh:123 --provider local --model qwen3-coder:30b

Options:
  --project DIR              Consumer repository (default: current directory)
  --provider codex|claude|ollama|local  Runtime (default: configured, then codex)
  --gear auto|0|1|2|3|4       Role-router gear preference
  --risk low|standard|high    Role-router risk class
  --model MODEL              Override model; required for a deterministic local run
  --dashboard auto|off       Start/reuse a local dashboard (default: auto)
  --dashboard-browser once|off  Open only on dashboard start (default: once)
  --auth subscription|api    Authentication (default: subscription; api is a per-run opt-in)
  --branch auto|NAME         Isolated ticket branch (default: auto)
  --push                     Commit verified changes and push the ticket branch
  --pr                       Open a PR after --push; never merges or deploys
  -h, --help                 Show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) shift; PROJECT="${1:-}" ;;
    --provider) shift; PROVIDER="${1:-}" ;;
    --model) shift; MODEL="${1:-}" ;;
    --gear) shift; export NIGHTSHIFT_GEAR="${1:-}" ;;
    --risk) shift; export NIGHTSHIFT_RISK="${1:-}" ;;
    --dashboard) shift; DASHBOARD="${1:-}" ;;
    --dashboard-browser) shift; DASHBOARD_BROWSER="${1:-}" ;;
    --auth) shift; AUTH_MODE="${1:-}"; AUTH_EXPLICIT=true ;;
    --branch) shift; BRANCH="${1:-}" ;;
    --push) PUSH="true" ;;
    --pr) OPEN_PR="true" ;;
    --batch-n|--resume)
      [ "$MODE" = "batch" ] || { echo "$1 is only valid with nightshift batch." >&2; exit 64; }
      BATCH_FLAG="$1"
      BATCH_ARGS+=("$BATCH_FLAG")
      shift
      [ -n "${1:-}" ] || { echo "$BATCH_FLAG requires a value." >&2; exit 64; }
      BATCH_ARGS+=("$1")
      ;;
    -h|--help) usage; exit 0 ;;
    --*) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    *)
      if [ "$1" = "batch" ] && [ -z "$REF" ] && [ "$MODE" = "eng" ]; then
        MODE="batch"
      elif [ "$MODE" = "batch" ]; then
        BATCH_ARGS+=("$1")
      elif [ -n "$REF" ]; then
        echo "Only one ticket reference is accepted." >&2; usage >&2; exit 64
      else
        REF="$1"
      fi
      ;;
  esac
  shift
done

[ "$MODE" = "batch" ] && [ "${#BATCH_ARGS[@]}" -eq 0 ] && { usage >&2; exit 64; }
[ "$MODE" = "eng" ] && [ -z "$REF" ] && { usage >&2; exit 64; }
[ -d "$PROJECT" ] || { echo "Project directory not found: $PROJECT" >&2; exit 66; }
if [ "$BRANCH" != none ] && ! git -C "$PROJECT" rev-parse --verify 'HEAD^{commit}' >/dev/null 2>&1; then
  echo 'nightshift: BASE_MISSING: isolated runs require an initial Git commit. Review and commit the starter files first; no model was started.' >&2
  exit 66
fi
case "${NIGHTSHIFT_GEAR:-auto}" in auto|0|1|2|3|4) ;; *) echo 'invalid --gear' >&2; exit 64 ;; esac
case "${NIGHTSHIFT_RISK:-standard}" in low|standard|high) ;; *) echo 'invalid --risk' >&2; exit 64 ;; esac
if ! bash "$SCRIPT_DIR/nightshift-manifest-validate.sh" --project "$PROJECT" >/dev/null 2>&1; then
  bash "$SCRIPT_DIR/nightshift-setup.sh" --project "$PROJECT" --ticket-ref "$REF" --runtime-provider "$PROVIDER" --runtime-model "$MODEL"
elif [ ! -e "$PROJECT/.nightshift.toml" ]; then
  bash "$SCRIPT_DIR/nightshift-setup.sh" --project "$PROJECT" --migrate
fi
bash "$SCRIPT_DIR/nightshift-manifest-validate.sh" --project "$PROJECT"
# Read data, never evaluate configuration as shell code.
SETTINGS_JSON="$(bash "$SCRIPT_DIR/nightshift-setup.sh" --project "$PROJECT" --read)"
GLOBAL_SETTINGS="$(bash "$SCRIPT_DIR/nightshift-setup.sh" --project "$NIGHTSHIFT_HOME_DIR" --read)"
PROJECT_SETTINGS="$SETTINGS_JSON"
SETTINGS_JSON="$(jq -cn --argjson global "$GLOBAL_SETTINGS" --argjson project "$SETTINGS_JSON" '$global * $project')"
[ -n "$PROVIDER" ] || PROVIDER="$(jq -r '.runtime.provider // "codex"' <<< "$SETTINGS_JSON")"
[ "$PROVIDER" != ollama ] || PROVIDER=local
[ -n "$MODEL" ] || MODEL="$(jq -r '.runtime.model // ""' <<< "$SETTINGS_JSON")"
LOCAL_MODEL="$(jq -r '.routing.local_model // ""' <<< "$SETTINGS_JSON")"
[ -z "$LOCAL_MODEL" ] || export NIGHTSHIFT_LOCAL_MODEL="$LOCAL_MODEL"
ROUTING_FILE="$(jq -r '.routing.file // .providers.routing_file // ""' <<< "$PROJECT_SETTINGS")"
ROUTING_BASE="$PROJECT"
if [ -z "$ROUTING_FILE" ]; then
  ROUTING_FILE="$(jq -r '.routing.file // .providers.routing_file // ""' <<< "$GLOBAL_SETTINGS")"
  ROUTING_BASE="$NIGHTSHIFT_HOME_DIR"
fi
if [ -n "$ROUTING_FILE" ]; then
  case "$ROUTING_FILE" in /*) ;; *) ROUTING_FILE="$ROUTING_BASE/$ROUTING_FILE" ;; esac
  export NIGHTSHIFT_ROUTING_FILE="$ROUTING_FILE"
fi
case "$PROVIDER" in codex|claude|local) ;; *) echo "Unknown provider: $PROVIDER" >&2; exit 64 ;; esac
[ -n "$BRANCH" ] || { echo "--branch requires auto, none, or a branch name." >&2; exit 64; }
[ "$OPEN_PR" = "false" ] || [ "$PUSH" = "true" ] || { echo "--pr requires --push." >&2; exit 64; }
RUNTIME_CLI=codex
[ "$PROVIDER" = claude ] && RUNTIME_CLI=claude
command -v "$RUNTIME_CLI" >/dev/null 2>&1 || { echo "$RUNTIME_CLI is required but was not found on PATH." >&2; exit 69; }

# The installer writes only this simple key. Do not source user configuration.
if [ -z "$AUTH_MODE" ] && [ -r "$AUTH_CONFIG" ]; then
  AUTH_MODE=$(grep -E '^NIGHTSHIFT_AUTH=(subscription|api)$' "$AUTH_CONFIG" 2>/dev/null | tail -1 | cut -d= -f2)
fi
[ -n "$AUTH_MODE" ] || AUTH_MODE="subscription"
case "$AUTH_MODE" in subscription|api) ;; *) echo "--auth requires subscription or api." >&2; exit 64 ;; esac
if [ "$AUTH_MODE" = api ] && [ "$AUTH_EXPLICIT" = false ]; then
  echo 'nightshift: saved API preference ignored; paid API use requires --auth api on this run.' >&2
  AUTH_MODE=subscription
fi
if [ "$AUTH_MODE" = subscription ]; then
  # Strip both providers' inherited billing credentials, including child tools.
  # Stored CLI settings/credentials still require the preflight checks below.
  unset OPENAI_API_KEY CODEX_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
  unset OPENAI_BASE_URL ANTHROPIC_BASE_URL
  unset CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
  echo 'nightshift: paid API mode disabled; no automatic billing fallback.' >&2
fi
echo "nightshift: installed build: $(bash "$SCRIPT_DIR/nightshift-version.sh" --project "$SOURCE_DIR")" >&2

if [ "$MODE" = "batch" ]; then
  REQUEST="\$nightshift batch ${BATCH_ARGS[*]}"
else
  QUOTED_REF=$(python3 -c 'import shlex,sys; print(shlex.quote(sys.argv[1]))' "$REF")
  REQUEST="\$nightshift ${QUOTED_REF}"
fi
REQUEST+=" --branch ${BRANCH}"
if [ "$AUTH_EXPLICIT" = true ] && [ "$AUTH_MODE" = api ]; then REQUEST+=" --auth api"; fi
if [ "$PROVIDER" = claude ]; then
  if [ "$MODE" = batch ]; then
    REQUEST="/nightshift-batch ${BATCH_ARGS[*]} --branch ${BRANCH}"
  else
    REQUEST="/nightshift-eng ${REF} --branch ${BRANCH}"
  fi
fi
[ "$PUSH" = "true" ] && REQUEST+=" --push"
[ "$OPEN_PR" = "true" ] && REQUEST+=" --pr"
# This Codex process is the factory worker. A literal command alone is ambiguous
# to an agent that also has the terminal launcher on PATH, which can recurse.
PROMPT="You are the inner Nightshift factory worker. Execute this requested Nightshift workflow directly by following its installed skill and command instructions: ${REQUEST}

Resolved factory policy: work only in clean isolated ticket worktrees; preserve the caller's dirty checkout; complete verified tickets through commit, ordinary push, and PR creation only. Do not deploy, merge a PR, request deployment environment details, or ask for production confirmation. Follow ticket dependencies in order. If a prerequisite is not yet merged, base a dependent ticket on the verified prerequisite branch and record the dependency; do not stop merely to ask whether to continue. Evidence failures get up to three smallest-scope repairs and then a durable failure receipt; continue independent later tickets.

Do not run the terminal launcher ('nightshift', 'drew', or 'scripts/nightshift-factory.sh') and do not start another Codex process. Those commands would recursively start a second factory. Perform the batch protocol and its per-ticket stages in this session instead."
SANDBOX="workspace-write"
if [ "$BRANCH" != "none" ]; then
  # Git creates refs and worktrees under .git; workspace-write intentionally
  # keeps that metadata read-only. This elevation is scoped to factory runs
  # that need branch hygiene and is never used for a branch-less run.
  SANDBOX="danger-full-access"
fi
COMMON=(--ask-for-approval never exec -C "$PROJECT" --sandbox "$SANDBOX")
[ -n "$MODEL" ] && COMMON+=(--model "$MODEL")

if [ "$PROVIDER" = "local" ]; then
  command -v ollama >/dev/null 2>&1 || { echo "ollama is required for --provider local." >&2; exit 69; }
  COMMON+=(--oss --local-provider ollama)
fi

if [ "$PROVIDER" = "codex" ] && [ "$AUTH_MODE" = "subscription" ]; then
  LOGIN_STATUS=$(env -u OPENAI_API_KEY codex login status 2>&1) || {
    echo "nightshift: ChatGPT subscription authentication is required." >&2
    echo "nightshift: run 'env -u OPENAI_API_KEY codex login' and choose Sign in with ChatGPT." >&2
    exit 77
  }
  if ! printf '%s\n' "$LOGIN_STATUS" | grep -qi 'Logged in using ChatGPT'; then
    echo "nightshift: expected ChatGPT subscription authentication, but Codex reports:" >&2
    printf '%s\n' "$LOGIN_STATUS" >&2
    echo "nightshift: run 'env -u OPENAI_API_KEY codex logout' then 'env -u OPENAI_API_KEY codex login'." >&2
    exit 77
  fi
  COMMON+=(-c 'forced_login_method="chatgpt"' -c 'model_provider="openai"')
  echo "nightshift: authentication: ChatGPT subscription (OPENAI_API_KEY ignored)." >&2
elif [ "$PROVIDER" = claude ]; then
  if [ "$AUTH_MODE" = subscription ]; then
    command -v jq >/dev/null 2>&1 || { echo 'jq is required to verify Claude authentication.' >&2; exit 69; }
    LOGIN_STATUS=$(cd "$PROJECT" && claude auth status --json 2>/dev/null) || {
      echo 'nightshift: cannot verify Claude subscription login; no API fallback.' >&2; exit 77;
    }
    if ! printf '%s\n' "$LOGIN_STATUS" | jq -e '.loggedIn == true and .authMethod == "claude.ai" and .apiProvider == "firstParty"' >/dev/null 2>&1; then
      echo 'nightshift: Claude subscription login required; run claude auth login first. No API fallback.' >&2
      exit 77
    fi
  fi
  echo "nightshift: runtime: Claude Code; using its configured login (auth preference: $AUTH_MODE)." >&2
elif [ "$PROVIDER" = local ]; then
  echo "nightshift: runtime: local Ollama." >&2
else
  echo "nightshift: authentication: API key billing." >&2
fi

[ -n "$DASHBOARD" ] || DASHBOARD="$(jq -r '.dashboard.mode // "auto"' <<< "$SETTINGS_JSON")"
[ -n "$DASHBOARD_BROWSER" ] || DASHBOARD_BROWSER="$(jq -r '.dashboard.browser // "once"' <<< "$SETTINGS_JSON")"
case "$DASHBOARD" in auto|off) ;; *) echo 'invalid dashboard mode' >&2; exit 64 ;; esac
case "$DASHBOARD_BROWSER" in once|off) ;; *) echo 'invalid dashboard browser mode' >&2; exit 64 ;; esac
if [ "$DASHBOARD" = auto ]; then
  python3 "$SCRIPT_DIR/nightshift-dashboard-start.py" --project "$PROJECT" --browser "$DASHBOARD_BROWSER" || true
fi
CHILD_PID=""
handle_interruption() {
  local signal="$1"
  echo "nightshift: interrupted by ${signal}; Codex was stopped before the factory completed." >&2
  if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
    kill -TERM "$CHILD_PID" 2>/dev/null || true
    wait "$CHILD_PID" 2>/dev/null || true
  fi
  echo "nightshift: inspect the batch state and resume with 'nightshift batch --resume <batch-file> --branch ${BRANCH}'." >&2
  exit 143
}
trap 'handle_interruption SIGINT' INT
trap 'handle_interruption SIGTERM' TERM

if [ "$PROVIDER" = claude ]; then
  CLAUDE_ARGS=(--print)
  [ "$BRANCH" != none ] && CLAUDE_ARGS+=(--dangerously-skip-permissions)
  [ -n "$MODEL" ] && CLAUDE_ARGS+=(--model "$MODEL")
  (
    cd "$PROJECT" || exit 66
    if [ "$AUTH_MODE" = subscription ]; then
      exec env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN claude "${CLAUDE_ARGS[@]}" "$PROMPT"
    else
      exec claude "${CLAUDE_ARGS[@]}" "$PROMPT"
    fi
  ) &
elif [ "$PROVIDER" = "codex" ] && [ "$AUTH_MODE" = "subscription" ]; then
  env -u OPENAI_API_KEY codex "${COMMON[@]}" "$PROMPT" &
else
  codex "${COMMON[@]}" "$PROMPT" &
fi
CHILD_PID=$!
set +e
wait "$CHILD_PID"
CODEX_STATUS=$?
set -e
CHILD_PID=""
if [ "$CODEX_STATUS" -eq 143 ]; then
  echo "nightshift: Codex received SIGTERM; inspect the batch state and resume instead of starting a fresh batch." >&2
fi
exit "$CODEX_STATUS"
