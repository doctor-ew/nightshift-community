#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-batch-terminal.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
git -C "$TMP_ROOT" init -q
git -C "$TMP_ROOT" config user.email test@example.invalid
git -C "$TMP_ROOT" config user.name test
mkdir -p "$TMP_ROOT/.nightshift"
STATE=.nightshift/batch-20260906-0000.json
cat > "$TMP_ROOT/$STATE" <<'JSON'
{"tickets":["first","second","third"],"current":"first","statuses":{"first":{"status":"in_progress","started_at":"start"},"second":{"status":"pending"},"third":{"status":"pending"}},"skip_reasons":{},"metrics":{}}
JSON
update() { CLAUDE_PROJECT_DIR="$TMP_ROOT" bash "$ROOT/scripts/nightshift-batch-update.sh" --state "$STATE" "$@"; }
update --ticket first --status blocked --receipt docs/first/failure.json --reason 'isolation unavailable'
jq -e '.current == null and .statuses.first.status == "blocked" and .statuses.first.receipt == "docs/first/failure.json" and .statuses.first.started_at == "start" and .statuses.second.status == "pending" and .metrics.blocked == 1 and .metrics.pending == 2' "$TMP_ROOT/$STATE" >/dev/null || fail 'blocked evidence was lost'
update --ticket second --status in_progress
update --ticket third --status needs-decision --receipt docs/third/decision.json --reason 'explicit decision'
jq -e '.current == "second" and .metrics.blocked == 1 and .metrics["needs-decision"] == 1 and .statuses.third.receipt == "docs/third/decision.json"' "$TMP_ROOT/$STATE" >/dev/null || fail 'independent terminal cleared current ticket'
update --ticket second --status complete --receipt docs/second/complete.json --pr-url https://example.invalid/pr/2
jq -e '.current == null and .metrics.complete == 1 and .metrics.blocked == 1 and .metrics["needs-decision"] == 1 and .statuses.second.receipt == "docs/second/complete.json" and .statuses.second.pr_url == "https://example.invalid/pr/2"' "$TMP_ROOT/$STATE" >/dev/null || fail 'later ticket cannot complete after blocked ticket'
update --ticket first --status failed --receipt docs/first/final.json --reason exhausted
jq -e '.metrics.failed == 1 and .metrics.blocked == 0 and .statuses.first.receipt == "docs/first/final.json" and .statuses.second.status == "complete"' "$TMP_ROOT/$STATE" >/dev/null || fail 'failure corrupted independent completion'
CLAUDE_PROJECT_DIR="$TMP_ROOT" bash "$ROOT/scripts/nightshift-batch-retro.sh" --state "$STATE"
grep -Fq '| Blocked | 0 |' "$TMP_ROOT/.nightshift/batch-null-retro.md" || fail 'retro hides blocked count'
grep -Fq '| Needs decision | 1 |' "$TMP_ROOT/.nightshift/batch-null-retro.md" || fail 'retro hides needs-decision count'
printf 'PASS: terminal batch evidence and continuation\n' 
