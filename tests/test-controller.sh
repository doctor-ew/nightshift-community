#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTROLLER="$ROOT/scripts/nightshift-controller.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-controller.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

mkdir -p "$TMP_ROOT/worktree"; git -C "$TMP_ROOT/worktree" init -q
git -C "$TMP_ROOT/worktree" config user.email test@example.invalid
git -C "$TMP_ROOT/worktree" config user.name test
printf 'seed\n' > "$TMP_ROOT/worktree/seed"; git -C "$TMP_ROOT/worktree" add seed; git -C "$TMP_ROOT/worktree" commit -qm seed

RECEIPT="$TMP_ROOT/receipt.json"
unset NIGHTSHIFT_WORKER_IMAGE
if "$CONTROLLER" run --ticket DP-0 --gate implement --provider codex --worktree "$TMP_ROOT/worktree" --receipt "$RECEIPT" --budget 1 --attempt-command 'touch host-bypass'; then
  fail 'controller accepted missing isolation image'
fi
[ ! -e "$TMP_ROOT/worktree/host-bypass" ] || fail 'command ran on host'
jq -e '.status == "blocked" and .attempts == [] and .provider == "codex" and .worktree != null and .repair_budget == 1 and .commands.attempt == "touch host-bypass" and .commands.repair == "" and (.output | length > 0) and (.changed_files | type == "array") and (.next_action | length > 0)' "$RECEIPT" >/dev/null || fail 'missing isolation receipt'

# Simulate only the engine boundary; this deliberately is not a real isolation test.
mkdir -p "$TMP_ROOT/bin"
cat > "$TMP_ROOT/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -eu
if [ "${1:-}" = info ]; then exit 0; fi
test "${1:-}" = run
shift
root=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --mount) root="${2#type=bind,src=}"; root="${root%%,dst=*}"; shift 2 ;;
    test-worker) shift; break ;;
    *) shift ;;
  esac
done
test -n "$root"
cd "$root"
exec "$@"
MOCK
chmod +x "$TMP_ROOT/bin/docker"
export PATH="$TMP_ROOT/bin:$PATH" NIGHTSHIFT_WORKER_IMAGE=test-worker NIGHTSHIFT_CONTAINER_RUNTIME=docker
"$CONTROLLER" run --ticket DP-1 --gate implement --provider codex --worktree "$TMP_ROOT/worktree" --receipt "$RECEIPT" --budget 2 --attempt-command 'test -f passed' --repair-command 'touch passed'
jq -e '.status == "complete" and .repair_budget == 2 and (.attempts | length) == 3 and .provider == "codex" and .next_action == "continue to the next gate"' "$RECEIPT" >/dev/null || fail 'successful convergence receipt is incomplete'
[ "$(wc -l < "$TMP_ROOT/policy-decisions.jsonl" | tr -d ' ')" -ge 3 ] || fail 'repair bypassed policy audit'

if "$CONTROLLER" run --ticket DP-2 --gate review --provider local --worktree "$TMP_ROOT/worktree" --receipt "$TMP_ROOT/failure.json" --budget 2 --attempt-command 'false'; then
  fail 'exhausted gate unexpectedly passed'
fi
jq -e '(.status == "failed") and ((.attempts | length) == 2) and (.next_action | contains("smallest in-scope"))' "$TMP_ROOT/failure.json" >/dev/null || fail 'failure receipt is incomplete'

# Every supported terminal failure retains command/output and never exceeds the cap.
for terminal in blocked needs-decision failed; do
  if "$CONTROLLER" run --ticket DP-3 --gate drift --provider local --worktree "$TMP_ROOT/worktree" --receipt "$TMP_ROOT/$terminal.json" --budget 3 --terminal-status "$terminal" --attempt-command 'echo failure; false' --repair-command 'echo repair; false'; then
    fail 'terminal failure unexpectedly passed'
  fi
  jq -e --arg terminal "$terminal" '.status == $terminal and .commands.attempt == "echo failure; false" and .commands.repair == "echo repair; false" and (.output | contains("failure")) and ([.attempts[] | select(has("attempt"))] | length) == 3 and ([.attempts[] | select(has("repair_after_attempt"))] | length) == 2 and (.changed_files | length > 0)' "$TMP_ROOT/$terminal.json" >/dev/null || fail 'terminal evidence or attempt cap is incorrect'
done
printf '[repair_budgets]\nqa = 1\n' > "$TMP_ROOT/worktree/nightshift.toml"
if "$CONTROLLER" run --ticket DP-4 --gate qa --provider local --worktree "$TMP_ROOT/worktree" --receipt "$TMP_ROOT/manifest.json" --attempt-command 'false' --repair-command 'touch must-not-repair'; then fail 'manifest gate unexpectedly passed'; fi
jq -e '.repair_budget == 1 and (.attempts | length) == 1' "$TMP_ROOT/manifest.json" >/dev/null || fail 'manifest gate budget not enforced'
[ ! -e "$TMP_ROOT/worktree/must-not-repair" ] || fail 'repair ran after exhausted budget'
# A failed dispatch does not prove the worker started. Simulate engine launch refusal.
cat > "$TMP_ROOT/bin/docker" <<'NOENGINE'
#!/usr/bin/env bash
printf 'engine unavailable; worker never launched\n' >&2
exit 69
NOENGINE
if "$CONTROLLER" run --ticket DP-5 --gate qa --provider codex --worktree "$TMP_ROOT/worktree" --receipt "$TMP_ROOT/launch.json" --budget 1 --attempt-command 'touch should-not-execute'; then fail 'engine refusal unexpectedly passed'; fi
[ ! -e "$TMP_ROOT/worktree/should-not-execute" ] || fail 'planned worker command executed'
jq -e '.status == "failed" and (.attempts | length) == 1 and .attempts[0].invocation == "isolation" and .attempts[0].worker_execution == "unknown" and .attempts[0].exit_code == 69 and (.output | contains("engine unavailable"))' "$TMP_ROOT/launch.json" >/dev/null || fail 'launch failure misrepresented as worker execution'
printf 'PASS: deterministic controller receipts\n'  
